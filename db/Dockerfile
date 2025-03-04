FROM postgres:15
ENV POSTGRES_USER=anon_user
ENV POSTGRES_PASSWORD=securepassword
ENV POSTGRES_DB=anon_db
COPY init.sql /docker-entrypoint-initdb.d/
