[app]
title = ClimbQuest
package.name = climbquest
package.domain = org.climbquest
presplash.color = #0B1D2E
presplash.filename = presplash.png
icon.filename = icon.png
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

[buildozer]
log_level = 2
warn_on_root = 1
