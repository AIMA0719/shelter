import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.kotlin.compose)
}

// 네이버 지도 NCP 키를 local.properties(NCP_KEY_ID) 또는 gradle 속성에서 읽는다.
// 키는 저장소에 커밋하지 않는다(local.properties 는 gitignore).
val naverNcpKeyId: String = run {
    val props = Properties()
    val lp = rootProject.file("local.properties")
    if (lp.exists()) lp.inputStream().use { props.load(it) }
    props.getProperty("NCP_KEY_ID")
        ?: (project.findProperty("naver.ncpKeyId") as String?)
        ?: "YOUR_NCP_KEY_ID"
}

android {
    namespace = "com.shelter.shade"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.shelter.shade"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"

        // gradle.properties 의 백엔드 주소를 BuildConfig 로 주입
        val apiBaseUrl: String = (project.findProperty("shelter.apiBaseUrl") as String?)
            ?: "http://10.0.2.2:8000/"
        buildConfigField("String", "API_BASE_URL", "\"$apiBaseUrl\"")

        // 네이버 지도 SDK 가 AndroidManifest 에서 읽는 NCP 키
        manifestPlaceholders["naverNcpKeyId"] = naverNcpKeyId
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation(libs.androidx.material.icons.extended)
    debugImplementation(libs.androidx.ui.tooling)

    implementation(libs.retrofit)
    implementation(libs.retrofit.kotlinx.serialization)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.okhttp.logging)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.naver.map.compose)
    implementation(libs.naver.map.sdk) // NCP_KEY_ID 인증 위해 map-sdk 3.21.0+ 강제
    implementation(libs.play.services.location) // 현재 위치(FusedLocationProviderClient)

    testImplementation(libs.junit)
}
