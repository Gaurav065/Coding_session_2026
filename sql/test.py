import re


email = "gaurav.patel2002@gmail.com"

def ext(email):
    first_name = email.split('.')

    last_name = first_name[1].split('@',)


    return first_name, last_name

print(ext(email=email))