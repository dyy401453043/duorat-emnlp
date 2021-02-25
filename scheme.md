* 针对schema-link的改动方案

| 问题描述 | 问题产生的原因 |改动思路 |
| :--- | :--- | :--- |
| question中**单引号**间的value不能完成link | bert分词器对单引号产生了影响 | 在bert分词前统一把单引号替换为双引号 |
| question中的单词和schema中的单词语义不关联，但产生了link(eg. question:average, schema:age) | 缺少schema到question的link过滤 | 在字符匹配的结果生成之后，计算question的单词glove向量和schema的单词glove向量，计算余弦相似度作为过滤条件，并且是双向过滤 |
| question中的单词和schema中的短语语义不关联，但产生了link(eg. question:number, schema:phone number) | 字符匹配的方式造成 | 在字符匹配的结果生成之后，添加一个question整句glove向量，与schema短语glove词向量之间的余弦相似度，作为过滤条件 |
| question中的单词和schema中的单词语义相关联，但没有产生link(eg. question:person, schema: people) | 字符匹配的方式造成 | 在字符匹配前之前，计算question中单词和schema单词的词向量相似度，若足够高，则直接作为link，但鉴于value太多，计算时间太长，暂时只在name的link上添加这个前置条件 |
| question中的常用单词与schema中的过多单词或短语产生了不正确的link(eg. question:name, schema: 各种name) | 字符匹配的方式造成 | 在完成所有匹配，已经生成link之后，检测question中每一个单词的link，如果这个单词的link数量大于某个阈值，则将这个单词的所有link舍弃 |
| 数据集中存在question正常，但schema内容为空 | 脏数据 | 影响不大，有时间可以统计一下数据，训练过程将这些数据筛掉

* 针对模型的改动方案
现在有通过图网络将表格建模的思路，优点在于能自然加入主外键关系（当作边），或者在模型阶段引入value，将value信息融入模型中。大方向就是强化利用schema信息。
