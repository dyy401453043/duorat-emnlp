# 简介

2021.3.13 dyy

验证集的大小为1034，存在314例有错误现象，分析了其中99例，查阅了这99例的link情况，数据库内容细节，得出本文结论。

按错误原因作分类，每类有样例展示和数量统计。未按难易程度分类，原因是，medium,hard,extra错误原因比较接近，easy错误主要是同义表达错误（与标准答案表述不同，但语义正确）。

需要注意的一点是，很多错误都与训练集较小（7000，还有接近半数的语义重复题），训练不足有关，我们的改进相当于在小样本训练情况下让模型表现更好。

模型预测结果具有不可解释性，无法明确知道错误产生的原因，错误分析的目的在于找到错误的分布情况，启发新的思路，融入信息帮助模型。

# 错误样例统计
## 连表错误
(21/99, 21.21%)
1. 对于question中的一些需求，模型的预测存在遗漏，对连表现象表现比较消极。但是连表可以通过主外键轻松得到，模型在这一块预测比较薄弱，也可能跟训练集较小训练不充分有关。
2. 连表的ON条件，有时候较为混乱，没有用键去连。

```json
    {
        "index": 43,
        "hardness": "hard",
        "pred": "SELECT Count(*) FROM stadium ORDER BY stadium.Capacity Desc LIMIT 1",
        "gold": "select count(*) from concert where stadium_id = (select stadium_id from stadium order by capacity desc limit 1)",
        "db_id": "concert_singer",
        "question": "Find the number of concerts happened in the stadium with the highest capacity .",
        "reason": "slack off"
    }
```

```json
    {
        "index": 83,
        "hardness": "hard",
        "pred": "SELECT Student.LName FROM Student JOIN Has_Pet ON Student.StuID = Has_Pet.StuID WHERE Student.Age = 3",
        "gold": "SELECT T1.lname FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T3.petid  =  T2.petid WHERE T3.pet_age  =  3 AND T3.pettype  =  'cat'",
        "db_id": "pets_1",
        "question": "Find the last name of the student who has a cat that is age 3.",
        "reason": "slack off, and link pet_age"
    }
```

```json
    {
        "index": 95,
        "hardness": "hard",
        "pred": "SELECT model_list.Model FROM model_list JOIN cars_data ON model_list.ModelId = cars_data.Id ORDER BY cars_data.Horsepower Asc LIMIT 1",
        "gold": "SELECT T1.Model FROM CAR_NAMES AS T1 JOIN CARS_DATA AS T2 ON T1.MakeId  =  T2.Id ORDER BY T2.horsepower ASC LIMIT 1;",
        "db_id": "car_1",
        "question": "Which model of the car has the minimum horsepower?",
        "reason": "slack off, wrong JOIN"
    }
```

## SELECT A FROM B错误
(18/99, 18.18%)

DUORAT模型的自由度较高，会产生这样一种现象，底层的原因模型可能还是对连表操作的消极表现。通过relation知道了要用两个或三个表的信息，但是没有将他们连接起来。

```json
    {
        "index": 97,
        "hardness": "extra",
        "pred": "SELECT model_list.Model FROM model_list WHERE cars_data.Weight < (SELECT Avg(cars_data.Weight) FROM cars_data)",
        "gold": "SELECT T1.model FROM CAR_NAMES AS T1 JOIN CARS_DATA AS T2 ON T1.MakeId  =  T2.Id WHERE T2.Weight  <  (SELECT avg(Weight) FROM CARS_DATA)",
        "db_id": "car_1",
        "question": "Find the model of the car whose weight is below the average weight.",
        "reason": "slack off, 'select A From B'"
    }
```

```json
    {
        "index": 103,
        "hardness": "hard",
        "pred": "SELECT DISTINCT model_list.Model FROM model_list WHERE cars_data.Year > 1980",
        "gold": "SELECT DISTINCT T1.model FROM MODEL_LIST AS T1 JOIN CAR_NAMES AS T2 ON T1.model  =  T2.model JOIN CARS_DATA AS T3 ON T2.MakeId  =  T3.id WHERE T3.year  >  1980;",
        "db_id": "car_1",
        "question": "Which distinct car models are the produced after 1980?",
        "reason": "slack off, 'select A From B'"
    }
```

```json
    {
        "index": 228,
        "hardness": "extra",
        "pred": "SELECT airports.AirportCode FROM flights GROUP BY flights.SourceAirport ORDER BY Count(*) Asc LIMIT 1",
        "gold": "SELECT T1.AirportCode FROM AIRPORTS AS T1 JOIN FLIGHTS AS T2 ON T1.AirportCode  =  T2.DestAirport OR T1.AirportCode  =  T2.SourceAirport GROUP BY T1.AirportCode ORDER BY count(*) LIMIT 1",
        "db_id": "flight_2",
        "question": "Give the code of the airport with the least flights.",
        "reason": "slack off, 'select A From B'"
    }
```

## 分组错误
(8/99, 8.08%)

这个错误比较小，通常是GROUP BY后的列选择错误，选择了一个与标准答案存在一一映射的列。通常选主键比较正确一些。

```json
    {
        "index": 36,
        "hardness": "medium",
        "pred": "SELECT singer.Name, Count(*) FROM singer_in_concert JOIN singer ON singer_in_concert.Singer_ID = singer.Singer_ID GROUP BY singer.Name",
        "gold": "SELECT T2.name ,  count(*) FROM singer_in_concert AS T1 JOIN singer AS T2 ON T1.singer_id  =  T2.singer_id GROUP BY T2.singer_id",
        "db_id": "concert_singer",
        "question": "What are the names of the singers and number of concerts for each person?",
        "reason": "GROUP BY condition"
    }
```

```json
    {
        "index": 90,
        "hardness": "medium",
        "pred": "SELECT continents.Continent, continents.Continent, Count(*) FROM continents JOIN countries ON continents.ContId = countries.Continent GROUP BY continents.Continent",
        "gold": "SELECT T1.ContId ,  T1.Continent ,  count(*) FROM CONTINENTS AS T1 JOIN COUNTRIES AS T2 ON T1.ContId  =  T2.Continent GROUP BY T1.ContId;",
        "db_id": "car_1",
        "question": "For each continent, list its id, name, and how many countries it has?",
        "reason": "both right, but why not use primary key after GROUP BY"
    }
```

## 其他错误
(39/99, 39.40%)

错误较多处，且原因较杂，包括SELECT一个列多次，列选择错误，复杂语法。
```json
    {
        "index": 128,
        "hardness": "medium",
        "pred": "SELECT Avg(cars_data.Weight), Avg(cars_data.Weight), cars_data.Year FROM cars_data GROUP BY cars_data.Year",
        "gold": "SELECT avg(Weight) ,  YEAR FROM CARS_DATA GROUP BY YEAR;",
        "db_id": "car_1",
        "question": "What is the average weight and year for each year?",
        "reason": "duplicated select"
    }
```

```json
    {
        "index": 16,
        "hardness": "medium",
        "pred": "SELECT Max(stadium.Capacity), Avg(stadium.Average) FROM stadium",
        "gold": "select max(capacity), average from stadium",
        "db_id": "concert_singer",
        "question": "What is the maximum capacity and the average of all stadiums ?",
        "reason": "misunderstand the 'average' in question and 'average' in column"
    }
```

```json
    {
        "index": 44,
        "hardness": "hard",
        "pred": "SELECT Count(*) FROM stadium JOIN concert ON stadium.Stadium_ID = concert.Stadium_ID ORDER BY stadium.Capacity Desc LIMIT 1",
        "gold": "select count(*) from concert where stadium_id = (select stadium_id from stadium order by capacity desc limit 1)",
        "db_id": "concert_singer",
        "question": "What are the number of concerts that occurred in the stadium with the largest capacity ?",
        "reason": "slack off"
    }
```

## 同义表达
(13/99, 13.13%)

语义相同，SQL语句略有不同，有比标准答案简单，也有比标准答案复杂。

```json
    {
        "index": 63,
        "hardness": "hard",
        "pred": "SELECT Student.StuID FROM Student EXCEPT SELECT Has_Pet.StuID FROM Has_Pet WHERE Pets.PetType = \" cat \"",
        "gold": "SELECT stuid FROM student EXCEPT SELECT T1.stuid FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T3.petid  =  T2.petid WHERE T3.pettype  =  'cat'",
        "db_id": "pets_1",
        "question": "Find the id of students who do not have a cat pet.",
        "reason": "both right"
    }
```

```json
    {
        "index": 67,
        "hardness": "medium",
        "pred": "SELECT Pets.PetType, Pets.weight FROM Pets WHERE Pets.pet_age = (SELECT Min(Pets.pet_age) FROM Pets)",
        "gold": "SELECT pettype ,  weight FROM pets ORDER BY pet_age LIMIT 1",
        "db_id": "pets_1",
        "question": "Find the type and weight of the youngest pet.",
        "reason": "both right, but more complicated"
    }
```

```json
    {
        "index": 168,
        "hardness": "extra",
        "pred": "SELECT car_names.MakeId, car_names.Make FROM cars_data JOIN car_names ON cars_data.Id = car_names.MakeId WHERE cars_data.Cylinders < 4 AND cars_data.Horsepower != (SELECT Min(cars_data.Horsepower) FROM cars_data)",
        "gold": "select t2.makeid ,  t2.make from cars_data as t1 join car_names as t2 on t1.id  =  t2.makeid where t1.horsepower  >  (select min(horsepower) from cars_data) and t1.cylinders  <  4;",
        "db_id": "car_1",
        "question": "Among the cars that do not have the minimum horsepower , what are the make ids and names of all those with less than 4 cylinders ?",
        "reason": "both right"
    }
```

#想到的方法

## “举例子法”

**出发点：**

在人的思维中，举例子的方式对抽象概念的理解非常有帮助。

对于许多高难度数据库，列名常常是专业名称或是一些在专业领域约定俗称的称呼，仅通过输入列名，模型难以理解该列真正的含义。

如果给每个column分配两个value作为对column的举例解释，将会对模型起很大的帮助。但这个过程中需要考虑到value的数量十分庞大，绝大多数都在十个以上。

目前初步的方案是使用最大，最小值两个value作为例子。大小顺序由主键列中的value来决定。直观来看，加入该方法有如下几个好处：

* 对于数值型value，最大，最小值能确定其范围，对列的选择有明显的参考意义，特别是当数值value无法在link中命中question中的数值时。（eg. index:152）
* 有些难度较大的数据库，列名是使用的专业名称，仅输入列名，模型难以得知其关联性，通过value举例提醒，再加之BERT对同类词的表征作用，能够帮助模型更好的理解列的含义（eg. flight_2, pet_age）。
* 对于主外键关系，在难度较大的数据库中，主键与外键的列名是不一致的，但主键与外键的value是一致的，输入value的边界，也就隐式输入强化了主外键关系。

**实现建模：**
* 在预处理阶段，获得列名的同时，查询获得列对于的value，取最大最小两个值，保存下来。
* 在输入BERT前，将输入方式改动为：
```text
[CLS]question [CLS]T1,...,[CLS]Tm [CLS]C1,...,[CLS]Cn
[CLS]question [CLS]T1,...,[CLS]Tm [CLS]C1[SEP]V1_min[SEP]V1_max,...,[CLS]Cn[SEP]Vn_min[SEP]Vn_max
```
* 经过BERT后，取T1...Tm，C1...Cn的[CLS]作表列的向量表示，这样value_min和value_max的内容就传递倒了对应的column中。

## “主外键嵌入”

**出发点：**

在SQL语言的CREATE语句建表时，需指定表名，列名，列类型，主键，外键引用。

这说明主外键也和表名，列名，列类型一样是数据库结构层面的基本信息， 将主外键在建模时进行嵌入是很有必要的。

在RAT中，已有对键关系的relation表征，但鉴于主外键的基本地位特性以及在对GROUP BY 和 JOIN时的指导作用，还是有必要对其进行更多的信息嵌入，尤其是在训练数据较小，训练不够充分的前提下。

通过错误样例驱动，直接键入主外键关系有如下好处：

* 在连表错误和SELECT A FROM B错误中，模型通过relation关系选择了正确的表列，但是模型对连表态度消极，不连表，甚至有胡乱连表的现象产生。（eg. index:95）如果有了主外键的关系的显示建模，连表就更加容易，至少人是这样来写连表语句的。
* 在GROUP BY错误中，虽然通过主键和通过与主键一一映射关系的列作分组依据都能取得正确结果，但通过主键分组更为标准，标准答案中也通常是通过主键分组，显示建模主键能帮助模型改正这一错误（eg. car_1）。

**实现建模：**
* 将question标0。Table标1。将主键（Primary Key）作特殊标识4。外键（Foreign Key）作另一种特殊表示3。其他列表2。生成embedding，加入Encoder的编码中。(有问题)

## 之前的一个bug记得修复

由于疏忽，之前相似度模块的OOV时值为None，使用时记得判断一下，是不是为none，不然age和pet_age，link不上。bug记得修复，有一些错误样例与此有关。

