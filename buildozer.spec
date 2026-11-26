[app]
presplash.filename = presplash.png
presplash.color = #0B1D2E
icon.filename = icon.png
title = ClimbQuest
package.name = climbquest
package.domain = org.climbquest
source.dir = .
source.include_exts = py
version = 1.0.0
requirements = python3,kivy==2.3.0
orientation = portrait
fullscreen = 1

android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True

# Pin python-for-android so it builds Python 3.11 (latest builds 3.14, which breaks Kivy 2.3.0)
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
