import random
import string

MB = 1024 ** 2


def random_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))


def test_error_exception():
    print("I am stdout")
    raise Exception("I am exceptional")


# Will error with NameError
def test_error_name_error():
    # noinspection PyUnresolvedReferences
    passs


def test_fail_assert():
    assert False


def test_fail_assert_long_output():
    output_size = 1 * MB
    print(random_generator(output_size))

    assert False


def test_success():
    pass
