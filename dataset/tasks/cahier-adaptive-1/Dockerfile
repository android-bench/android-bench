FROM romanofranz-cahier-base
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV GRADLE_OPTS="-Xmx6g"
RUN cd /workspace/testbed && \
    git reset --hard 70a3500788b28a261c900ff4bc442bf08f295738 && \
    git remote remove origin || true && \
    git branch | grep -v '*' | xargs git branch -D || true && \
    TARGET_TIMESTAMP=$(git show -s --format=%ct 70a3500788b28a261c900ff4bc442bf08f295738) && \
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
