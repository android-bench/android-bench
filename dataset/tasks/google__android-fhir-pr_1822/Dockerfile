FROM google-android-fhir-base
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ENV GRADLE_OPTS="-Xmx6g"
RUN cd /workspace/testbed && \
    git reset --hard b143c6c7c9fac00ef2d9623f7a4a171f3da2a82b && \
    git remote remove origin || true && \
    git branch | grep -v '*' | xargs git branch -D || true && \
    TARGET_TIMESTAMP=$(git show -s --format=%ct b143c6c7c9fac00ef2d9623f7a4a171f3da2a82b) && \
    git tag -l | while read tag; do \
        TAG_COMMIT=$(git rev-list -n 1 "$tag"); \
        TAG_TIME=$(git show -s --format=%ct "$TAG_COMMIT"); \
        if [ "$TAG_TIME" -gt "$TARGET_TIMESTAMP" ]; then \
            git tag -d "$tag"; \
        fi; \
    done && \
    git reflog expire --expire=now --all && \
    git gc --prune=now --aggressive && \
    sed -i 's/ratchetFrom = "origin\/master"/\/\/ratchetFrom = "origin\/master"/' buildSrc/src/main/kotlin/SpotlessConfig.kt && git update-index --assume-unchanged buildSrc/src/main/kotlin/SpotlessConfig.kt && ./gradlew assembleDebug
WORKDIR /workspace/testbed
