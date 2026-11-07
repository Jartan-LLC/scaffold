# packaging/rpm.sh builds this spec. Write no percent sign in a comment: rpm expands
# macros there too.
# TODO(/onboard): the package name. Each release attaches the RPM as NAME.noarch.rpm.
Name:           app
# packaging/rpm.sh defines tag_version from the release tag.
Version:        %{tag_version}
# One package for every Fedora release, so no dist suffix.
Release:        1
Summary:        TODO(/onboard): the package's one-line summary
# TODO(/onboard): the SPDX identifier of LICENSE.
License:        MIT
# TODO(/onboard): replace ORG/REPO with the GitHub org and repo.
URL:            https://github.com/ORG/REPO
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

%description
TODO(/onboard): what the package does, in a sentence or two.

%prep
%autosetup

%install
# TODO(/onboard): install the project's files under the buildroot, list them under files
# below, and add a Requires line for each command they run.

%check
# TODO(/onboard): run the project's tests. A failure fails the build.

%files
%license LICENSE
%doc README.md
