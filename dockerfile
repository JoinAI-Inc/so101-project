FROM python:3.10-slim


RUN mkdir /code

WORKDIR  /code


COPY  requirements.txt  requirements.txt
RUN   pip install -r  requirements.txt  -i  http://mirrors.aliyun.com/pypi/simple/ --trusted-host=mirrors.aliyun.com


COPY  app  app

COPY  docker/docker-entrypoint.sh  /docker-entrypoint.sh


EXPOSE 8000

CMD ["/bin/bash","/docker-entrypoint.sh"]
