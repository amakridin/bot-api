FROM docker.unixrepo.domain.ru/bot-base:1.0
LABEL maintainer=amakridin \
    description="Docker image for bot_api"
  
RUN mkdir -p /data/bot/ini && mkdir -p /data/bot/static/css && mkdir -p /data/bot/templates && mkdir /data/sock && chmod a+rw -R /data/sock && mkdir /data/bot/json && \
    chmod a+rw -R /data/bot/json && mkdir /data/bot/temp && chmod a+rw -R /data/bot/temp && mkdir /data/bot/sql && chmod a+rw -R /data/bot/sql
COPY ["main.py","get_params.py","db_data.py","redis_data.py","ldap.py","rand.py","send2tamtam.py","zbx.py","config", "/data/bot/"]
COPY api/api.ini /data/bot/ini
COPY sql/im.sql /data/bot/sql
COPY static/css/main.css /data/bot/static/css/main.css
COPY templates/diag.html /data/bot/templates/diag.html
#RUN adduser -u 10006 nginx
COPY api/nginx.conf /etc/nginx/nginx.conf 
RUN mkdir -p /var/cache/nginx &&\ 
    chown -R nginx:nginx /var/cache/nginx &&\
    chown -R nginx:nginx /var/log/nginx/ &&\
    chown -R nginx:nginx /etc/nginx/conf.d &&\
    chown -R nginx:nginx /usr/share/nginx
RUN touch /var/run/nginx.pid &&\ 
    chown -R nginx:nginx /var/run/nginx.pid
#RUN chmod -R  a+rw /var/log/
EXPOSE 5002
ENV LANG=en_US.UTF-8
#USER nginx 
RUN echo 'nginx -c /etc/nginx/nginx.conf & uwsgi --emperor=/data/bot/ini'>/data/bot/start.sh && chmod +x /data/bot/start.sh
WORKDIR /data/bot
CMD ./start.sh
