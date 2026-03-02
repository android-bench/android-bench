FROM googlemaps-android-maps-compose-base
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV GRADLE_OPTS="-Xmx6g"
RUN cd /workspace/testbed && \
    git reset --hard b22fab2c1213bd80185c666ae387fc33050ab776 && \
    git remote remove origin || true && \
    git branch | grep -v '*' | xargs git branch -D || true && \
    TARGET_TIMESTAMP=$(git show -s --format=%ct b22fab2c1213bd80185c666ae387fc33050ab776) && \
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
