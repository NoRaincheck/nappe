
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

def unused_function():
    x = 1
    y = 2
    return x + y

class MyClass:
    def method(self):
        return self

if __name__ == "__main__":
    for i in range(10):
        print(fibonacci(i))
