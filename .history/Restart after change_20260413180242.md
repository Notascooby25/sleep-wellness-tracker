1. Restart the frontend container
bash

docker-compose restart frontend

This is usually enough because Streamlit reloads the file on container restart.

🔥 2. If the page still shows the old version, fully recreate the container
bash

docker-compose stop frontend
docker-compose rm -f frontend
docker-compose up -d frontend


🧹 3. If you changed the Dockerfile or build context, rebuild the image
Only needed if you edited the Dockerfile or anything in frontend/ that gets copied during build.

bash

docker-compose build --no-cache frontend
docker-compose up -d frontend



🔁 4. Hard refresh your browser
Streamlit sometimes caches aggressively in the browser.

Press:

Ctrl + Shift + R

This forces the browser to reload the page and ignore cached scripts