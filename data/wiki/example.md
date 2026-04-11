# Python 装饰器

## 定义

**装饰器(Decorator)** 是 Python 中一种用于在**不修改原函数源码**的情况下扩展函
数行为的设计模式。它本质上是一个**接收函数并返回新函数**的可调用对象。

## 原理

`@decorator` 语法是 `func = decorator(func)` 的语法糖。Python 在函数定义时自动
应用装饰器,等价于:

```python
def greet(name):
    return f"hello, {name}"
greet = log_calls(greet)
```

## 示例

```python
from functools import wraps

def log_calls(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        print(f"calling {func.__name__}")
        return func(*args, **kwargs)
    return wrapper

@log_calls
def greet(name):
    return f"hello, {name}"
```

调用 `greet("world")` 时会先打印 `calling greet`,再返回 `"hello, world"`。

## 常见用途

- **日志**:在函数前后打印调用信息
- **缓存**:`functools.lru_cache`
- **权限校验**:Web 框架里的 `@login_required`
- **重试**:网络请求失败后自动重试
- **性能埋点**:统计函数执行时间

## 注意事项

务必使用 `functools.wraps`,否则被装饰函数的 `__name__`、`__doc__`、`__module__`
等元信息会被 `wrapper` 覆盖。

## 总结

装饰器是 Python 提供的「**给函数包一层**」的标准手法,干净、可组合、定义即生效。

---

> 这是 `compile_note()` 把 `data/raw/example.md` 经过 LLM 整理后产出的示例
> wiki 文件。真实 wiki 文件已被 `.gitignore` 排除。
