1. Restart the frontend-web container
bash

docker-compose restart frontend_web

This is usually enough for configuration-only changes.

2. If the page still shows the old version, fully recreate the container
bash

docker-compose stop frontend_web
docker-compose rm -f frontend_web
docker-compose up -d frontend_web


3. If you changed the Dockerfile or build context, rebuild the image
Only needed if you edited anything in frontend-web/ that is copied during build.

bash

docker-compose build --no-cache frontend_web
docker-compose up -d frontend_web



4. Hard refresh your browser
Browser cache can still show stale assets.

Press:

Ctrl + Shift + R

This forces the browser to reload the page and ignore cached scripts