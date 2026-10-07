# LensPrompt release (R8) rules.
#
# Most libraries (Compose, CameraX, ML Kit, coroutines) ship their own consumer
# rules. The exceptions are the offline speech stack:

# JNA: binds Java declarations to native code by reflection (Native.register,
# Structure fields, callbacks) and is loaded from native code by name.
-keep class com.sun.jna.** { *; }
-keepclassmembers class * extends com.sun.jna.** { public *; }
-dontwarn java.awt.**
-dontwarn com.sun.jna.**

# Vosk: Java side of libvosk, registered through JNA direct mapping.
-keep class org.vosk.** { *; }

# Keep line numbers for readable Play Console crash reports (the mapping file is
# uploaded with the bundle); hide the original source file name.
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile
