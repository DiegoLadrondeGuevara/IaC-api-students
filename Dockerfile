FROM python:3-slim
WORKDIR /programas/api-students
RUN pip3 install flask
COPY . .
RUN python3 db.py
EXPOSE 8000
CMD [ "python3", "./app.py" ]