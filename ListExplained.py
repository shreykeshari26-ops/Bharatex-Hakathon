#WAP to ask the user to enter names of their 3 favorite movies & store them in a list.
movies = []
print("Enter Your 3 favorite movies : ")
for i in range(3):
    name = input(f"movie {i+1} : ")
    movies.append(name)
print("Your Movies Are : ",movies)







#WAP to count the number of students with the “A” grade in the following tuple.
"""list = ["C", "D", "A", "A", "B", "B", "A"]
count = 0
for i in range(7):
    if list[i]=="A":
        count = count+1
print(count)"""