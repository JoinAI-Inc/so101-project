
import json

from fastapi import FastAPI


from appclass import app_class

app = FastAPI()


@app.get("/")
def read_root():

    name = app_class.do_something()

    response = {
        "Hello": name
    }


    return  json.dumps(response)
   