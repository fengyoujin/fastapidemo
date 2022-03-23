from enum import Enum
from typing import Optional, List, Set
from fastapi import FastAPI, Query, Path, Body, Cookie, Header, status, Form, UploadFile, responses, HTTPException, Depends, Request
from pydantic import BaseModel, Field, EmailStr
from uuid import UUID
from datetime import datetime, time, timedelta
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# swagger UI：http://127.0.0.1:8000/docs
# ReDoc： http://127.0.0.1:8000/redoc
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/items/{id}", response_class=responses.HTMLResponse)
async def read_item3(request: Request, id: str):
    return templates.TemplateResponse("item.html", {"request": request, "id": id})


async def verify_token(x_token: str = Header(...)):
    if x_token != "fake-super-secret-token":
        raise HTTPException(status_code=400, detail="X-Token header invalid")


async def verify_key(x_key: str = Header(...)):
    if x_key != "fake-super-secret-key":
        raise HTTPException(status_code=400, detail="X-Key header invalid")
    return x_key

# 在app里设定全局依赖项
# app = FastAPI(dependencies=[Depends(verify_token), Depends(verify_key)])
# Tips：1. 同一路径同一方法会被覆盖,但会调用前一个接口的方法
#       2. 带有默认值的参数放在没有默认值的参数前，Python会报错
#       3. 为解决第二点，一定要有参数先后排序可以使用*作为函数的第一个参数，
#          Python 不会对该 * 做任何事情，但是它将知道之后的所有参数都应作为关键字参数（键值对）
#       4. tags 参数为路径操作添加标签
#       5. jsonable_encoder可以对Pydantic model进行一些转换(like a dict, list, etc)
#       6. 利用PUT，PATCH更新数据时注意Pydantic model定义的默认值，如没传会将默认值更新进DB，可以用item.dict(exclude_unset=True)排除默认值

# 添加OAuth2进行身份验证
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@app.get("/")
async def root(token: str = Depends(oauth2_scheme)):
    return {"message": "Hello World", "token": token}


fake_items_db = [{"item_name": "Foo"}, {"item_name": "Bar"}, {"item_name": "Baz"}]


class ModelName(str, Enum):
    alexnet = "alexnet"
    resnet = "resnet"
    lenet = "lenet"


# list查询 --fake_items_db
# dict更新新增 --results.update
# 必须参数 --skip
# 必须参数默认值定义 --limit
# 用Query额外校验 --a
# 正则表达式校验 --b
# 用Query (...)必选+校验 --c
# 用List 接收参数 --d
# 为参数添加其他信息，如title，description --d
# 参数别名alias="item-query" --d
# 表示参数已弃用 deprecated=True --b
# 大于gt，小于lt --
# 大于等于ge，小于等于le
@app.get("/items/", tags=['items'], summary="Get an item")
async def read_item(
    skip: int,
    limit: int = 10,
    a: Optional[str] = Query(None, max_length=50),
    b: Optional[str] = Query(None, regex="^fixedquery$", deprecated=True),
    c: str = Query(..., min_length=1),
    d: Optional[List[str]] = Query(None, alias="item-query", title='Query string', description='Query string for the items to search in the database'),
    e: int = Query(..., title="The ID of the item to get", gt=0, lt=1000),
    f: float = Query(..., title="The ID of the item to get", ge=0, le=10.5)
):
    # 利用文档字符串可以对接口做描述，支持MarkDown
    """
    Create an item with all the information:

    - **name**: each item must have a name
    - **description**: a long description
    - **price**: required
    - **tax**: if the item doesn't have tax, you can omit this
    - **tags**: a set of unique tag strings for this item
    """
    results = {"items": [{"item_id": "Foo"}, {"item_id": "Bar"}]}
    if a:
        results.update({"a": a})
    return {
        "a": fake_items_db[skip: skip + limit],
        "b": b,
        "c": c,
        "d": d,
        "e": e,
        "f": f
    }


# 多路径查询参数
# Enum 路径参数 --model_name
@app.get("/users/{user_id}/items/{model_name}", tags=['users'])
async def read_user_item(
    user_id: int, model_name: ModelName
):
    if model_name == ModelName.alexnet:
        return {"model_name": model_name, "message": "Deep Learning FTW!"}

    if model_name.value == "lenet":
        return {"model_name": model_name, "message": "LeCNN all the images"}
    return {"model_name": model_name, "message": "Have some residuals"}


# 文件路径
@app.get("/files/{file_path:path}", tags=['files'])
async def read_file(file_path: str):
    return {"file_path": file_path}


# 通过使用 Config 和 schema_extra 为Pydantic模型声明一个示例
class Item(BaseModel):
    name: str
    description: Optional[str] = Field(
        None, title="The description of the item", max_length=300
    )
    price: float = Field(..., gt=0, description="The price must be greater than zero")
    tax: Optional[float] = None,
    # tags: list[str] = []  # 声明子类型的List
    tags: Set[str] = set()  # 导入 Set 并将 tag 声明为一个由 str 组成的 set,确保每一个str都是唯一的,重复的会被转换为唯一项输入和输出

    class Config:
        schema_extra = {
            "example": {
                "name": "Foo",
                "description": "A very nice Item",
                "price": 35.4,
                "tax": 3.2,
            }
        }


# 请求体+路径参数+查询参数
# 为path添加验证和其他信息 --item_id
# 用response_model=Item 定义相应的模型
# status_code=status.HTTP_201_CREATED 定义成功的状态码
@app.post("/items/{item_id}", response_model=Item, status_code=status.HTTP_201_CREATED,  tags=['items'])
# 报错提示第二点
# async def create_item(item_id: int = Path(..., title="The ID of the item to get"), item: Item, q: Optional[str] = None):
# 用*作为函数的第一个参数解决
# async def create_item(*, item_id: int = Path(..., title="The ID of the item to get"), item: Item, q: Optional[str] = None):
async def create_item(item: Item, q: Optional[str] = None, item_id: int = Path(..., title="The ID of the item to get")):
    return {"item_id": item_id, **item.dict()}


class User(BaseModel):
    username: str
    full_name: Optional[str] = None


# 多个请求体参数
# body 请求 --importance
# 利用Body的embed=True生成一个特殊的请求参数,Item -- Item
# 使用 Pydantic 的 Field 在 Pydantic 模型内部声明校验和元数据 -- Item
@app.put("/items/{item_id}", tags=['items'])
async def update_item(item_id: int, item: Item = Body(..., embed=True)):
    # async def update_item(item_id: int, item: Item, user: User, importance: int = Body(...)):
    # results = {"item_id": item_id, "item": item, "user": user, "importance": importance}
    results = {"item_id": item_id, "item": item}
    return results


# 额外的数据类型
# UUID:
# 一种标准的 "通用唯一标识符" ，在许多数据库和系统中用作ID。
# 在请求和响应中将以 str 表示。
# datetime.datetime:
# 一个 Python datetime.datetime.
# 在请求和响应中将表示为 ISO 8601 格式的 str ，比如: 2008-09-15T15:53:00+05:00.
# datetime.date:
# Python datetime.date.
# 在请求和响应中将表示为 ISO 8601 格式的 str ，比如: 2008-09-15.
# datetime.time:
# 一个 Python datetime.time.
# 在请求和响应中将表示为 ISO 8601 格式的 str ，比如: 14:23:55.003.
# datetime.timedelta:
# 一个 Python datetime.timedelta.
# 在请求和响应中将表示为 float 代表总秒数。
# Pydantic 也允许将其表示为 "ISO 8601 时间差异编码", 查看文档了解更多信息。
# frozenset:
# 在请求和响应中，作为 set 对待：
# 在请求中，列表将被读取，消除重复，并将其转换为一个 set。
# 在响应中 set 将被转换为 list 。
# 产生的模式将指定那些 set 的值是唯一的 (使用 JSON 模式的 uniqueItems)。
# bytes:
# 标准的 Python bytes。
# 在请求和相应中被当作 str 处理。
# 生成的模式将指定这个 str 是 binary "格式"。
# Decimal:
# 标准的 Python Decimal。
# 在请求和相应中被当做 float 一样处理。
# 您可以在这里检查所有有效的pydantic数据类型: Pydantic data types.
@app.put("/test1/{item_id}", tags=['test1'])
async def read_test1(
    item_id: UUID,
    start_datetime: Optional[datetime] = Body(None),
    end_datetime: Optional[datetime] = Body(None),
    repeat_at: Optional[time] = Body(None),
    process_after: Optional[timedelta] = Body(None),
):
    start_process = start_datetime + process_after
    duration = end_datetime - start_process
    return {
        "item_id": item_id,
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "repeat_at": repeat_at,
        "process_after": process_after,
        "start_process": start_process,
        "duration": duration,
    }


# Cookie 参数
# 使用 Cookie 声明 cookie 参数，使用方式与 Query 和 Path 类似。
@app.get("/cookie/", tags=['items'])
async def read_cookie(ads_id: Optional[str] = Cookie(None)):
    return {"ads_id": ads_id}


# Header 参数
# 使用 Header 声明 Header 参数，使用方式与 Query 和 Path 类似。
# 默认情况下Header 会将参数名称的字符从下划线(_)转换为连字符(-)来提取记录headers 可以用convert_underscores=False禁止这一自动转换
# header重复出现的情况下可以用list 的形式获得重复header的所有值
@app.get("/header/", tags=['header'])
# async def read_header(ux_token: Optional[List[str]] = Header(None)):
async def read_header(user_agent: Optional[str] = Header(None)):
    return {"user_agent": user_agent}


# 当响应模型中定义了默认值，而使用过程中不想返回默认值时可以用response_model_exclude_unset=True进行控制
# response_model_exclude_defaults=True
# response_model_exclude_none=True
# response_model_include 和 response_model_exclude 可以自定义响应模型,但不建议使用,因为会导致OpenAPI 定义 JSON Schema 仍将是完整的模型。
# response_model_include=["name", "description"],
class res(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tax: float = 10.5
    tags: List[str] = []


ress = {
    "foo": {"name": "Foo", "price": 50.2},
    "bar": {"name": "Bar", "description": "The bartenders", "price": 62, "tax": 20.2},
    "baz": {"name": "Baz", "description": None, "price": 50.2, "tax": 10.5, "tags": []},
}


@app.patch("/res/{item_id}", response_model=res, tags=['res'])
async def update_item1(item_id: str, item: res):
    stored_item_data = ress[item_id]
    stored_item_model = Item(**stored_item_data)
    update_data = item.dict(exclude_unset=True)
    updated_item = stored_item_model.copy(update=update_data)
    ress[item_id] = jsonable_encoder(updated_item)
    return updated_item


# 用HTTPException处理异常错误
# 可以用参数 detail 传递任何能转换为 JSON 的值，不仅限于 str。
# 还支持传递 dict、list 等数据结构。
# FastAPI 能自动处理这些数据，并将之转换为 JSON
@app.get("/res/{item_id}", response_model=res, response_model_exclude_unset=True, tags=['res'])
async def read_res(item_id: str):
    if item_id not in ress:
        raise HTTPException(status_code=404, detail="Item not found")
    return ress[item_id]


# 数据在不同模型中的转换.dict()
class UserIn(BaseModel):
    username: str
    password: str
    email: EmailStr
    full_name: Optional[str] = None


class UserOut(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None


class UserInDB(BaseModel):
    username: str
    hashed_password: str
    email: EmailStr
    full_name: Optional[str] = None


def fake_password_hasher(raw_password: str):
    return "supersecret" + raw_password


def fake_save_user(user_in: UserIn):
    hashed_password = fake_password_hasher(user_in.password)
    # **user_in.dict()利用Pydantic  UserInDB模型将user_in解包, 然后添加额外的关键字参数 hashed_password=hashed_password
    user_in_db = UserInDB(**user_in.dict(), hashed_password=hashed_password)
    print("User saved! ..not really")
    return user_in_db


@app.post("/user/", response_model=UserOut, tags=['user'])
async def create_user(user_in: UserIn):
    user_saved = fake_save_user(user_in)
    return user_saved


# 以上模型中包含大量的重复定义，为此可用继承的方式减少代码的重复
# class UserBase(BaseModel):
#     username: str
#     email: EmailStr
#     full_name: Optional[str] = None


# class UserIn(UserBase):
#     password: str


# class UserOut(UserBase):
#     pass


# class UserInDB(UserBase):
#     hashed_password: str

# 定义form 参数
# OAuth2 规范的 "密码流" 模式规定要通过表单字段发送 username 和 password。
# 表单数据的「媒体类型」编码一般为 application/x-www-form-urlencoded
# 可在一个路径操作中声明多个 Form 参数，但不能同时声明要接收 JSON 的 Body 字段。因为此时请求体的编码是 application/x-www-form-urlencoded，不是 application/json。
@app.post("/login/", tags=['user'])
async def login1(username: str = Form(...), password: str = Form(...)):
    return {"username": username}


# 请求文件
# UploadFile 支持以下 async 方法，（使用内部 SpooledTemporaryFile）可调用相应的文件方法。

# write(data)：把 data （str 或 bytes）写入文件；
# read(size)：按指定数量的字节或字符（size (int)）读取文件内容；
# seek(offset)：移动至文件 offset （int）字节处的位置；
# 例如，await myfile.seek(0) 移动到文件开头；
# 执行 await myfile.read() 后，需再次读取已读取内容时，这种方法特别好用；
# close()：关闭文件
@app.post("/uploadfile/", tags=['user'])
async def create_upload_file(file: UploadFile):
    return {"filename": file.filename}


# 多文件上传 用List接收UploadFile
# async def create_upload_files(files: List[UploadFile]):
#     return {"filenames": [file.filename for file in files]}
@app.get("/fileFrom/", tags=['user'])
async def main():
    content = """
<body>
<form action="/files/" enctype="multipart/form-data" method="post">
<input name="files" type="file" multiple>
<input type="submit">
</form>
<form action="/uploadfiles/" enctype="multipart/form-data" method="post">
<input name="files" type="file" multiple>
<input type="submit">
</form>
</body>
    """
    return responses.HTMLResponse(content=content)


# 依赖项注入,与以下术语等同
# 资源（Resource）
# 提供方（Provider）
# 服务（Service）
# 可注入（Injectable）
# 组件（Component）
async def common_parameters(q: Optional[str] = None, skip: int = 0, limit: int = 100):
    return {"q": q, "skip": skip, "limit": limit}


@app.get("/dependency1/", tags=['dependency'])
async def read_items(commons: dict = Depends(common_parameters)):
    """
    接收到新的参数时,FastAPI执行如下操作:
    - 用正确的参数调用依赖项函数
    - 获取函数的返回结果
    - 把函数返回的结果赋值给路径操作函数的参数
    ![依赖项](https://d33wubrfki0l68.cloudfront.net/eab45e25bb79970178fab7a2d10cba0209372a59/94d9e/assets/images/philly-magic-garden.jpg)
    """
    return commons


def query_extractor(q: Optional[str] = None):
    return q


def query_or_cookie_extractor(
    q: str = Depends(query_extractor), last_query: Optional[str] = Cookie(None)
):
    if not q:
        return last_query
    return q


# 子依赖项 query_extractor
# 多次使用同一依赖项时FastAPI只会调用一次，第二次会取缓存中的值，可以使用use_cache=False避免使用缓存
@app.get("/dependency2/", tags=['dependency'])
async def read_users(commons: dict = Depends(query_or_cookie_extractor)):
    return commons


# 装饰器中添加dependencies参数不需要依赖项的解析值，但需要执行依赖项
@app.get("/dependency3/", tags=['dependency'], dependencies=[Depends(verify_token), Depends(verify_key)])
async def read_dependency3():
    return [{"item": "Foo"}, {"item": "Bar"}]


fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "fakehashedsecret",
        "disabled": False,
    },
    "alice": {
        "username": "alice",
        "full_name": "Alice Wonderson",
        "email": "alice@example.com",
        "hashed_password": "fakehashedsecret2",
        "disabled": True,
    },
}


class UserInfo(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None


def fake_decode_token(token):
    return UserInfo(
        username=token + "fakedecoded", email="john@example.com", full_name="John Doe"
    )


class UserInDB1(UserInfo):
    hashed_password: str


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB1(**user_dict)


def fake_hash_password(password: str):
    return "fakehashed" + password


def fake_decode_token1(token):
    # This doesn't provide any security at all
    # Check the next version
    user = get_user(fake_users_db, token)
    return user


async def get_current_user(token: str = Depends(oauth2_scheme)):
    user = fake_decode_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_user(token: str = Depends(oauth2_scheme)):
    user = fake_decode_token1(token)
    return user


@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user_dict = fake_users_db.get(form_data.username)
    if not user_dict:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    user = UserInDB(**user_dict)
    hashed_password = fake_hash_password(form_data.password)
    if not hashed_password == user.hashed_password:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    return {"access_token": user.username, "token_type": "bearer"}


@app.get("/users/me", tags=['users'],)
async def read_users_me(current_user: UserInfo = Depends(get_current_active_user)):
    return current_user
