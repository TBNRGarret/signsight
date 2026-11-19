"""Optional offline Gradle probe, including a Flutter-like included build."""
import os
from pathlib import Path
import subprocess

import pytest


@pytest.mark.skipif(not os.environ.get("SIGNSIGHT_TEST_GRADLE_BIN"), reason="opt-in Gradle fixture")
def test_ci_mirror_covers_settings_projects_and_included_build(tmp_path):
    init = Path(__file__).resolve().parents[1] / ".github/gradle/central-mirror.init.gradle"
    mirror = "https://maven-central.storage-download.googleapis.com/maven2/"
    included = tmp_path / "included"
    included.mkdir()
    for directory in (tmp_path, included):
        settings = f"""
pluginManagement {{
    repositories {{ gradlePluginPortal() }}
    assert repositories.first().url.toString() == '{mirror}'
}}
dependencyResolutionManagement {{
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {{ google(); mavenCentral() }}
}}
assert dependencyResolutionManagement.repositories.find {{ it.name == 'MavenRepo' }}.url.toString() == '{mirror}'
rootProject.name = '{directory.name}'
"""
        if directory == tmp_path:
            settings = settings.replace("RepositoriesMode.FAIL_ON_PROJECT_REPOS", "RepositoriesMode.PREFER_PROJECT")
            settings += "\nincludeBuild('included')\n"
        (directory / "settings.gradle").write_text(settings)
        build = f"""
buildscript {{ repositories {{ mavenCentral() }} }}
assert buildscript.repositories.first().url.toString() == '{mirror}'
"""
        if directory == tmp_path:
            build += f"repositories {{ mavenCentral() }}\nassert repositories.first().url.toString() == '{mirror}'\n"
        build += "tasks.register('checkRepositories') { doLast { println('REPOSITORIES_OK') } }\n"
        (directory / "build.gradle").write_text(build)
    env = dict(os.environ, GRADLE_USER_HOME=str(tmp_path / "gradle-home"))
    result = subprocess.run([
        os.environ["SIGNSIGHT_TEST_GRADLE_BIN"], "--offline", "--no-daemon", "--console=plain",
        "--init-script", str(init), "checkRepositories", ":included:checkRepositories",
    ], cwd=tmp_path, env=env, text=True, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("REPOSITORIES_OK") == 2
