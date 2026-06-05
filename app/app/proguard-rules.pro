# kotlinx.serialization
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**
-keepclassmembers class com.shelter.shade.data.** {
    *** Companion;
}
-keepclasseswithmembers class com.shelter.shade.data.** {
    kotlinx.serialization.KSerializer serializer(...);
}
