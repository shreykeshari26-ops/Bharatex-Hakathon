'''def linear_search(my_list, key):
    for i in range(len(my_list)):
        if my_list[i] == key:
            return i
    return -1'''
def binary_search(my_list,key):
    low=0
    high = len(my_list)-1

    while low <= high:
        mid = (low + high ) // 2
        if my_list[mid] == key :
            return mid
        elif key > my_list[mid]:
            low = mid + 1
        else:
            high = mid - 1
    return - 1 
my_list = [1,1,3,3,3,5,5,5,5,7]
result = binary_search(my_list,8)
if result != -1:
    print(f"Element found at index - {result}")
else:
    print("element not found")
        

