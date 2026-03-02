FROM google-android-fhir-base
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ENV GRADLE_OPTS="-Xmx6g"
RUN cd /workspace/testbed && \
    git reset --hard c232eb5166fcb17e8940c6770b8e817c5bfed86c && \
    git remote remove origin || true && \
    git branch | grep -v '*' | xargs git branch -D || true && \
    TARGET_TIMESTAMP=$(git show -s --format=%ct c232eb5166fcb17e8940c6770b8e817c5bfed86c) && \
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
