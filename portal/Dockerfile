FROM mcr.microsoft.com/azurelinux/base/nginx:1.25
COPY nginx.conf /etc/nginx/nginx.conf
COPY site/ /usr/share/nginx/html/
RUN chmod -R a+rX /usr/share/nginx/html && chmod 644 /etc/nginx/nginx.conf
EXPOSE 80

COPY start.sh /start.sh
RUN chmod 755 /start.sh
CMD ["/bin/sh", "/start.sh"]
