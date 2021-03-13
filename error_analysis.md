# 简介

2021.3.13

验证集的大小为1034，存在314例有错误现象，分析了其中99例，查阅了这99例的link情况，数据库内容细节，得出以下结论。

按错误原因作分类，每类有一些举例和数量统计。未按难易程度分类，medium,hard,extra错误原因比较接近，easy错误主要是同义（与标准答案不同，但语义正确）。

需要注意的一点是，很多错误都与训练集较小（7000，还有接近半数的语义重复题），训练不足有关。

# 错误样例统计
## 连表错误
(21/99, 21.21%)
1. 对于question中的一些需求，模型的预测存在遗漏，对连表现象表现比较消极。但是连表可以通过主外键轻松得到，模型在这一块预测比较薄弱，也可能跟训练集较小训练不充分有关。
2. 连表的ON条件，有时候较为混乱，没有用键去连。

```json
    {
        "index": 23,
        "hardness": "medium",
        "pred": "SELECT concert.Stadium_ID, Count(*) FROM concert GROUP BY concert.Stadium_ID",
        "gold": "SELECT T2.name ,  count(*) FROM concert AS T1 JOIN stadium AS T2 ON T1.stadium_id  =  T2.stadium_id GROUP BY T1.stadium_id",
        "db_id": "concert_singer",
        "question": "For each stadium, how many concerts play there?",
        "reason": "a little slack off"
    }
```

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

DUORAT模型的自由度较高，会产生这样一种现象，底层的原因模型可能还是对连表操作的消极表现。

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

错误较多处，且原因较杂，包括SELECT一个列多次，条件列选择错误，复杂语法。

```json
    {
        "index": 5,
        "hardness": "medium",
        "pred": "SELECT Avg(singer.Age), Min(singer.Age), Max(singer.Age) FROM singer WHERE singer.Age = \" m \"",
        "gold": "SELECT avg(age) ,  min(age) ,  max(age) FROM singer WHERE country  =  'France'",
        "db_id": "concert_singer",
        "question": "What is the average, minimum, and maximum age for all French singers?",
        "reason": "duplicated SELECT, WHERE condition error, no-link between France and French"
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

## 不同表达
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