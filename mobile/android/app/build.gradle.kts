plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Signing secrets belong to the build environment, never to source control.
val releaseSigning = listOf(
    "SIGNSIGHT_KEYSTORE_PATH", "SIGNSIGHT_STORE_PASSWORD",
    "SIGNSIGHT_KEY_ALIAS", "SIGNSIGHT_KEY_PASSWORD",
).associateWith { System.getenv(it)?.takeIf(String::isNotBlank) }
val hasReleaseSigning = releaseSigning.values.all { it != null }

gradle.taskGraph.whenReady {
    if (allTasks.any { it.project == project && it.name.contains("Release") } && !hasReleaseSigning) {
        throw GradleException("Release signing requires all SIGNSIGHT_KEYSTORE_PATH, SIGNSIGHT_STORE_PASSWORD, SIGNSIGHT_KEY_ALIAS and SIGNSIGHT_KEY_PASSWORD environment variables.")
    }
}

android {
    namespace = "app.signsight.signsight_user"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "app.signsight.signsight_user"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("release") {
            if (hasReleaseSigning) {
                storeFile = file(releaseSigning.getValue("SIGNSIGHT_KEYSTORE_PATH")!!)
                storePassword = releaseSigning.getValue("SIGNSIGHT_STORE_PASSWORD")
                keyAlias = releaseSigning.getValue("SIGNSIGHT_KEY_ALIAS")
                keyPassword = releaseSigning.getValue("SIGNSIGHT_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
