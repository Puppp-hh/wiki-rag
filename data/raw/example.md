# Python 装饰器示例笔记

这是一份示例 raw 笔记,说明你可以怎么往 `data/raw/` 里塞东西。

随便写,不用结构、不用排版,想到啥写啥。后面 `python main.py compile` 会让 LLM
把它整理成 `data/wiki/` 下的结构化版本。

---

装饰器是 python 里很常见的语法糖,本质上就是把一个函数当成参数传给另一个函数,
然后返回一个新函数。`@decorator` 这个写法等价于 `func = decorator(func)`。

举个例子:

```python
def log_calls(func):
    def wrapper(*args, **kwargs):
        print(f"calling {func.__name__}")
        return func(*args, **kwargs)
    return wrapper

@log_calls
def greet(name):
    return f"hello, {name}"
```

调用 `greet("world")` 之前会先打印 `calling greet`。

常见用途:日志、缓存、权限校验、重试、性能埋点。

写装饰器的时候记得用 `functools.wraps`,否则被装饰函数的 `__name__` / `__doc__`
会被覆盖。

---

> 这只是个示例文件。把你自己的真实笔记放进 `data/raw/`,真实文件已经被
> `.gitignore` 排除掉,不会被推到 GitHub。
