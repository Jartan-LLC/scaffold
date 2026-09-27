# The activation record (.git/liza/activation.json) that shim.sh writes and deactivate.sh
# undoes: {legacy, settings, files, overwritten, exclude_lines}.
#
# settings holds the changes activation made to settings.local.json, each one of:
#   {op: "add-elem", path, value}    an array element activation added
#   {op: "rem-elem", path, value}    an array element activation replaced
#   {op: "set", path, before, after} a scalar activation set; before is null when absent
#   {op: "created", path}            a container that didn't exist before activation
# files holds {path, fp} for each file activation created, fp from activation-lib.sh's
# fingerprint, so a file edited since can be kept. overwritten holds the same for each
# user file init overwrote, whose original shim.sh keeps under .git/liza/originals/.
# exclude_lines are the lines activation added to .git/info/exclude.

def _changes($pre; $post; $path):
  if ($post | type) == "object" and ($pre == null or ($pre | type) == "object") then
    (if $pre == null then [{op: "created", path: $path}] else [] end)
    + ([$post | keys[] as $k | _changes($pre[$k]; $post[$k]; $path + [$k])] | add // [])
  elif ($post | type) == "array" and ($pre == null or ($pre | type) == "array") then
    ($pre // []) as $p
    | (if $pre == null then [{op: "created", path: $path}] else [] end)
      + [$post[] as $e | select(any($p[]; . == $e) | not) | {op: "add-elem", path: $path, value: $e}]
      + [$p[] as $e | select(any($post[]; . == $e) | not) | {op: "rem-elem", path: $path, value: $e}]
  elif $pre == $post then []
  else [{op: "set", path: $path, before: $pre, after: $post}]
  end;

def changes($pre; $post): _changes($pre; $post; []);

# Folds a re-activation's changes into the record. An element a later activation drops
# that an earlier one added cancels out, so it isn't restored later; a key set twice
# keeps its original value.
def merge_changes($old; $new):
  [$new[] | select(.op == "rem-elem") | [.path, .value]] as $dropped
  | [$old[] | select(.op == "add-elem" and ([.path, .value] as $a | any($dropped[]; . == $a)))
    | [.path, .value]] as $cancelled
  | [$old[] | select(.op != "add-elem" or ([.path, .value] as $a | any($cancelled[]; . == $a) | not))]
    + [$new[] | select(.op != "rem-elem" or ([.path, .value] as $r | any($cancelled[]; . == $r) | not))]
  | ([.[] | select(.op != "set")] | unique)
    + [[.[] | select(.op == "set")] | group_by(.path)[]
       | {op: "set", path: .[0].path, before: .[0].before, after: .[-1].after}];

def revert($changes):
  reduce ($changes | map(select(.op != "created")) | reverse[]) as $c (.;
    getpath($c.path) as $cur
    | if $c.op == "add-elem" then
        if ($cur | type) == "array" then setpath($c.path; [$cur[] | select(. != $c.value)]) else . end
      elif $c.op == "rem-elem" then
        if $cur == null then setpath($c.path; [$c.value])
        elif ($cur | type) == "array" and (any($cur[]; . == $c.value) | not) then setpath($c.path; $cur + [$c.value])
        else . end
      elif $cur == $c.after then
        if $c.before == null then delpaths([$c.path]) else setpath($c.path; $c.before) end
      else . end)
  | reduce ($changes | map(select(.op == "created")) | sort_by(.path | length) | reverse[]) as $c (.;
      if $c.path != [] and (getpath($c.path) | . == {} or . == []) then delpaths([$c.path]) else . end);

def _entries: split("\n") | map(select(. != "") | capture("^(?<path>.*) (?<fp>[^ ]+)$"));
def _listed($list): . as $e | any($list[]; .path == $e.path);

# Folds one activation into the record (the input). The string arguments are fingerprint
# output: the worktree files init created, the files already recorded before and after
# init (one this init rewrote takes its new fingerprint), and the git dir's hooks and
# liza* files before and after, and the user files init overwrote (a later rewrite of
# one updates its fingerprint). $exclude_added is the lines added to the exclude file.
def record_activation($pre; $post; $created; $recorded_before; $recorded_after;
                      $git_before; $git_after; $overwritten; $exclude_added):
  ($recorded_before | _entries) as $rb
  | ($git_before | _entries) as $gb
  | ($overwritten | _entries) as $ow
  | .overwritten = ([(.overwritten // [])[] | select(_listed($ow) | not)] + $ow)
  | [$recorded_after | _entries | .[] | . as $e | select(any($rb[]; .path == $e.path and .fp != $e.fp))]
    as $rewritten
  | .settings = merge_changes(.settings; changes($pre; $post))
  | .files = ([.files[] | select(_listed($rewritten) | not)] + $rewritten + ($created | _entries)
      + [$git_after | _entries | .[] | select(_listed($gb) | not)] | unique_by(.path))
  | .exclude_lines = (.exclude_lines + ($exclude_added | split("\n") | map(select(. != ""))) | unique);

# The fallback for a clone activated before records existed: hooks recognizably Liza's.
def _is_liza_hook($liza_home): (.command // "") | contains($liza_home) or test("\\.claude/hooks/");
def has_liza_hooks($liza_home): any(.hooks[]?[]?.hooks[]?; (.command // "") | contains($liza_home));
def liza_hook_scripts($liza_home):
  [.hooks[]?[]?.hooks[]? | select(_is_liza_hook($liza_home)) | .command
   | capture("(?<p>\\.claude/hooks/[^\" ]+)").p] | unique;
def drop_liza_hooks($liza_home):
  if .hooks == null then . else
    (.hooks |= (map_values(map(.hooks |= map(select(_is_liza_hook($liza_home) | not)))
                           | map(select(.hooks | length > 0)))
                | with_entries(select(.value | length > 0))))
    | if .hooks == {} then del(.hooks) else . end
  end;
