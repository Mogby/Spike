docker rm spike_bot 2>/dev/null || true
docker build . -t spike_bot_image && docker run --name spike_bot spike_bot_image
