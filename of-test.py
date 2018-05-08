# ryu-manager yourapp.py

from ryu.base import app_manager

class Layer2Switch(app_manager.RyuApp):

    def __init__(self, *args, **kwargs):
        super(Layer2Switch, self).__init__(*args, **kwargs)

    
