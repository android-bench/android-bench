FROM googlemaps-android-maps-compose-base
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ENV GRADLE_OPTS="-Xmx6g"
RUN cd /workspace/testbed && \
    git reset --hard c8673cd26fb9d80bff8e5bd8e1626475cb9d8956 && \
    git remote remove origin || true && \
    git branch | grep -v '*' | xargs git branch -D || true && \
    TARGET_TIMESTAMP=$(git show -s --format=%ct c8673cd26fb9d80bff8e5bd8e1626475cb9d8956) && \
    git tag -l | while read tag; do \
        TAG_COMMIT=$(git rev-list -n 1 "$tag"); \
        TAG_TIME=$(git show -s --format=%ct "$TAG_COMMIT"); \
        if [ "$TAG_TIME" -gt "$TARGET_TIMESTAMP" ]; then \
            git tag -d "$tag"; \
        fi; \
    done && \
    git reflog expire --expire=now --all && \
    git gc --prune=now --aggressive && \
    ./gradlew assembleDebug
WORKDIR /workspace/testbed
