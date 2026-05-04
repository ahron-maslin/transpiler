def add(a: int, b: int) -> int:
    return a + b


def is_even(n: int) -> bool:
    if n % 2 == 0:
        return True
    else:
        return False


def main():
    x: int = 10
    y: int = 20
    print(add(x, y))
