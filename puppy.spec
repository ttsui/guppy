%define name puppy
%define version 1.11
%define release 1

Summary: Command line Topfield PVR File Downloader
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{name}_%{version}_src.tar.bz2
License: GNU Public License
Group: Applications/Multimedia
BuildRoot: %{_tmppath}/%{name}_%{version}-%{release}-buildroot
Prefix: %{_prefix}
Packager: Tony Tsui <tsui.tony@gmail.com>
Url: http://puppy.sourceforge.net

%description
Puppy is a command line tool for downloading and uploading of files to a
Topfield PVR.

%prep
%setup -n puppy_1.11

%build
make

%install
install -D puppy ${RPM_BUILD_ROOT}/%{_bindir}/puppy

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
%{_bindir}/puppy
