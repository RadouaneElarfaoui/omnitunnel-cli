import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.tunnel import Tun
class injector_init_():
    def __init__(self):
        self.Tun = Tun()
    def main(self):
        self.Tun.create_connection()
        
        
     
if __name__=="__main__":
    run= injector_init_()
    run.main()
       
       
