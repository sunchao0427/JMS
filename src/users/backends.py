from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.conf import settings

from utilities.security.cryptography import PubPvtKey
from filemanager.models import FileManagerSettings

import pexpect, base64, requests

class ImpersonatorBackend(ModelBackend):
    
    key_file = settings.JMS_SETTINGS["user_processes"]["key"]
    imp_url = "http://127.0.0.1:%s/impersonate" % settings.JMS_SETTINGS["user_processes"]["port"]
    
    def authenticate(self, username=None, password=None):
        
        # get the user if it exists; if it doesn't exist, create the user
        user = None
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist, ex:
            user = User.objects.create(username=username, email="", password="")
        
        # encrypt and encode password for transmission and to store in DB
        encoded = ""
        with open(self.key_file, "r") as key_fd:
            key = key_fd.read()
            encrypted = PubPvtKey.encrypt(key, str("%s:%s" % (username, password)))
            encoded = base64.b64encode(encrypted)                
        
        # send encoded, encrypted password to impersonator server for authentication   
        if self.linux_auth(encoded):
            fm_settings, created = FileManagerSettings.objects.get_or_create(User=user)
            fm_settings.ServerPass = base64.b64encode(encrypted)
            fm_settings.save()                
            
            return user
        else:
            return None
       
    def linux_auth(self, encoded):
        data = "%s\n%s\nprompt" % (encoded, "whoami")
        r = requests.post(self.imp_url, data=data)
        return r.status_code == requests.codes.ok



class LinuxBackend(ModelBackend):
    
    def authenticate(self, username=None, password=None):
        try:
            user = User.objects.get(username=username)            
            
            if self.linux_auth(username, password):
                user.set_password(password)
                user.userprofile.Code = password
                user.userprofile.save()
                user.save()
                return user
            
        except User.DoesNotExist:
        	
            if self.linux_auth(username, password):
        	    user = User.objects.create(username=username, email='', password=password)
        	    user.userprofile.Code = password
        	    user.userprofile.save()
        	    return user
            else:
                return None
            
        return None 
    
       
    def linux_auth(self, username=None, password=None):
        child = pexpect.spawn('su - %s' % username)
        child.expect('Password:')
        child.sendline (password)
        
    	i = child.expect (['su: Authentication failure', '[#\$] '], timeout=6)
        child.close(force=True)
            
        return i == 1
