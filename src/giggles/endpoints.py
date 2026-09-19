"""Backend paths, transcribed from the ``com.giggles.mb`` v3.1.2 bundle dump.

Paths that take an id are ``str.format`` templates. Keep this the only place a
path is spelled so a server-side rename is a one-line fix. Nothing here is a
guarantee: the dump lists paths and query names, not response shapes, which is
what the recorder in :mod:`giggles.client` exists to learn.
"""

# --- discovery ---------------------------------------------------------------
FEED = "/api/v3/feed"
FEED_RANDOM = "/api/videos/random"
MOST_INCREASED = "/api/v3/explore/most-increased"
HASHTAGS_NEWEST = "/api/v2/hashtags/newest"
POSTS_SEARCH = "/api/v3/posts/search"
POST = "/api/v2/posts/{post_id}"
POST_SIMILAR = "/api/v3/posts/{post_id}/similar"
USER_POSTS = "/api/v3/users/{user_id}/posts"
AUDIOS_TOP = "/api/audios/top"

# --- video market ------------------------------------------------------------
POST_INVEST = "/api/posts/{post_id}/invest"
POST_MARKET_GRAPH = "/api/posts/{post_id}/market/graph"
POST_MARKET_TRADES = "/api/posts/{post_id}/market/trades"
POST_MARKET_INVESTORS = "/api/posts/{post_id}/market/comment-investors"
POST_GRAPH_ALL = "/api/posts/{post_id}/graph/all"

# --- portfolio and ledger ----------------------------------------------------
PORTFOLIO = "/api/v2/portfolio-v2"
PORTFOLIO_V3 = "/api/v3/portfolio"
CLOSED_POSITIONS = "/api/v2/portfolio/closed-positions"
TRANSACTIONS = "/api/v3/transactions"
USER_PORTFOLIO = "/api/v2/users/{user_id}/portfolio"
LEADERBOARD = "/api/v3/leaderboard"

# --- account -----------------------------------------------------------------
PROFILE = "/api/user/profile"
USER_VIDEOS = "/api/user/videos"
CHECK_AURA = "/api/user/check-aura"
STARTUP = "/api/startup"

# --- aura faucets ------------------------------------------------------------
REWARDS = "/api/v3/rewards"
REWARDS_CLAIM = "/api/v3/rewards/claim"
GIFT_STATUS = "/api/v3/gift/status"
GIFT_REVEAL = "/api/v3/gift/reveal"
TRENDS_CLAIM_SIGNUP = "/api/v3/trends/claim-signup"
SUBSCRIPTION_PERKS = "/api/v3/subscription/perks"

# --- trend cards -------------------------------------------------------------
CARDS_CATALOG = "/api/v3/cards/catalog"
CARDS_INVENTORY = "/api/v3/cards/inventory"
CARDS_BOXES = "/api/v3/cards/boxes"
CARDS_STORE = "/api/v3/cards/store"
CARDS_MARKET_LOTS = "/api/v3/cards/market/lots"
CARDS_MARKET_AUCTIONS = "/api/v3/cards/market/auctions"
CARDS_MARKET_SEARCH = "/api/v3/cards/market/search"
CARDS_TRADES = "/api/v3/cards/trades"

# --- real time ---------------------------------------------------------------
CENTRIFUGO_CONNECTION_TOKEN = "/api/v2/centrifugo/connection-token"  # noqa: S105 (a path)
CENTRIFUGO_SUBSCRIPTION_TOKEN = "/api/v2/centrifugo/subscription-token"  # noqa: S105 (a path)
