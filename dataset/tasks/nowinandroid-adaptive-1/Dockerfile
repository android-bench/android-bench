FROM android-bench-env
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
COPY android/nowinandroid /workspace/testbed
ENV GRADLE_OPTS="-Xmx6g"
RUN cd /workspace/testbed && \
    git remote remove origin || true && \
    git branch | grep -v '*' | xargs git branch -D || true && \
    TARGET_TIMESTAMP=$(git show -s --format=%ct change-1020) && \
    git tag -l | while read tag; do \
        TAG_COMMIT=$(git rev-list -n 1 "$tag"); \
        TAG_TIME=$(git show -s --format=%ct "$TAG_COMMIT"); \
        if [ "$TAG_TIME" -gt "$TARGET_TIMESTAMP" ]; then \
            git tag -d "$tag"; \
        fi; \
    done && \
    git reflog expire --expire=now --all && \
    git gc --prune=now --aggressive && \
    ./gradlew assembleDemoDebug
WORKDIR /workspace/testbed
