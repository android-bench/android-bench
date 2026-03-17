import docker
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def cleanup_images(all_images=False):
    client = docker.from_env()
    
    # Task images usually follow the pattern android__*
    # Base images follow android-* (like android-nowinandroid-base)
    # The environment image is android-bench-env
    
    logger.info("Starting Docker resource cleanup...")
    
    try:
        # 1. Remove stopped containers to free up space
        logger.info("Pruning stopped containers...")
        client.containers.prune()
        
        # 2. Identify images to remove
        images = client.images.list()
        to_remove = []
        
        for img in images:
            for tag in img.tags:
                # Always remove task images
                if tag.startswith("android__"):
                    to_remove.append(tag)
                # Remove base and env images only if 'all' is specified
                elif all_images and (tag.startswith("android-") or tag == "android-bench-env:latest"):
                    to_remove.append(tag)
        
        if not to_remove:
            logger.info("No relevant images found for removal.")
            return

        for tag in sorted(list(set(to_remove))):
            try:
                logger.info(f"Removing image: {tag}")
                client.images.remove(image=tag, force=True)
            except Exception as e:
                logger.warning(f"Could not remove {tag}: {e}")
        
        # 3. Prune build cache to reclaim massive amounts of disk space
        logger.info("Pruning build cache...")
        client.api.prune_build_cache()
        
        logger.info("Cleanup complete.")
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup Docker resources for Android Bench.")
    parser.add_argument("--all", action="store_true", help="Remove all images, including base and environment images.")
    args = parser.parse_args()
    
    cleanup_images(all_images=args.all)
