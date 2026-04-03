#tuple wagerah class ka
"""def create_tup(*args):
    print("recived arguments : ",args)
    print("Type : ", type(args))
    return args
result1 = create_tup(1,2,3,4)"""

#zip function use and tuple creation and typecast
"""t1 = (4,5,2,5,8,3,2,4,1)
t2 = tuple(sorted(t1))
t3 = tuple(zip(t1,t2))
print(t3)"""

#same thing but typecast in list
"""t1 = (4,5,2,5,8,3,2,4,1)
t2 = list(sorted(t1))
t3 = list(zip(t1,t2))
print(t3)"""

#Learning sets
"""s1 = {10,"shaurya",2.89}
s1.add("verma")
s1.add(4)
print(s1)
s1.remove("shaurya")
print(s1)"""

#set-function fuction etc
"""s1 = {1,4,2,8,3}
s2 = {1,2,3}
s3 = {7,8,9}
print(s2.issubset(s1))
print(s1.issuperset(s2))
print(s1.union(s3))
print(s1.intersection(s2))
print(s1.difference(s2))"""
#file handling
"""f = open("E:\Downloads\ReadMe.txt","r")
print(f.read())
print(f.tell())
print(f.read(5))
print(f.seek(0))
print(f.read(5))
print(f.tell())"""
#idk
import json
student = {
    "Vansh" : 80,
    "Rahul" : 70,
    "Isha"  : 50
}
f = open("Record.json","w")
json.dump(student,f)
f.close()
f=open("Record.json","r")
print(f.read())
data = json.load(f)
f["Vansh"]



