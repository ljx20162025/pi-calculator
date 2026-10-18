[app]

# (str) Title of your application
# NOTE: keep this file pure ASCII - buildozer reads it with the
# container locale, which is often POSIX (ASCII) and would choke on CJK.
title = Pi Calculator

# (str) Package name
package.name = picalc

# (str) Package domain (needed for android/ios packaging)
package.domain = org.example

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas

# (list) Application requirements
requirements = python3,kivy

# (str) Application versioning (method 1)
version = 1.0

# (str) Supported orientation: landscape, portrait, sensorLandscape or all
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions - this app needs none
# android.permissions = INTERNET

# (int) Target Android API, should be as high as possible.
android.api = 34

# (int) Minimum API your APK / AAB will support.
# Must be >= 24: CPython's remote_debugging.c uses preadv()/pwritev(),
# which only exist in Android's bionic from API 24 (Android 7.0) onwards.
# With 23 the NDK headers do not declare them and the build dies with
# "implicit declaration of function 'preadv' is invalid in C99 [-Werror]".
android.minapi = 24

# (int) Android NDK API to use - kept in sync with android.minapi.
android.ndk_api = 24

# (str) Android NDK version to use
android.ndk = 25b

# (bool) Enable AndroidX support (required by current python-for-android)
android.enable_androidx = True

# (bool) Automatically accept the Android SDK license agreements.
# Required in CI: without it sdkmanager prints "Accept? (y/N)", reads EOF,
# defaults to N, and silently skips build-tools - which later shows up as
# the misleading "Aidl not found, please install it" error.
android.accept_sdk_license = True

# (list) Android architecture to build for.
# arm64-v8a covers virtually all modern phones and builds much faster
# than also including armeabi-v7a.
android.archs = arm64-v8a

# (bool) Copy python instead of compiling it (faster builds, bigger apk)
# android.use_ndk_legacy = False

[buildozer]

# (int) Display error if buildozer is run as root
warn_on_root = 0

# (int) Log level: 0 error only, 1 info, 2 debug
log_level = 2
