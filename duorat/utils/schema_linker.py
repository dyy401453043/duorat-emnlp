import abc
import json
from collections import deque

import _jsonnet
from dataclasses import replace
from typing import (
    Tuple,
    Generator,
    Optional,
    Callable,
    Iterable,
    Sequence,
)

from duorat.preproc.slml import SLMLBuilder
from duorat.preproc.utils import has_subsequence
from duorat.types import (
    SQLSchema,
    ValueMatchTag,
    HighConfidenceMatch,
    TableMatchTag,
    ColumnMatchTag,
    TaggedToken,
    TaggedSequence,
    LowConfidenceMatch,
    MatchConfidence,
)
from duorat.utils import registry
from duorat.utils.db_content import (
    pre_process_words,
    match_db_content,
    EntryType,
)
from duorat.utils.tokenization import AbstractTokenizer
from nltk.corpus import stopwords
import nltk 
stop_words = set(stopwords.words("english")).union({".", "?", "," })
stemmer = nltk.PorterStemmer()
import copy
import torch
import torchtext
from torchtext.vocab import GloVe
glove_6b_100d = torchtext.vocab.GloVe(name='6B',dim=100,cache='./glove/')

def similarity(str1:str, str2:str):
    vector1 = torch.mean(glove_6b_100d.get_vecs_by_tokens(str1.split(' ')), dim=0, keepdim=False)
    vector2 = torch.mean(glove_6b_100d.get_vecs_by_tokens(str2.split(' ')), dim=0, keepdim=False)
    nomlized_v1 = vector1 / torch.norm(vector1)
    nomlized_v2 = vector2 / torch.norm(vector2)
    return torch.dot(nomlized_v1,nomlized_v2).numpy()

class AbstractSchemaLinker(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def question_to_slml(self, question: str, sql_schema: SQLSchema) -> str:
        pass


MATCH_CONFIDENCE = {
    "high": HighConfidenceMatch(),
    "low": LowConfidenceMatch(),
    "none": None,
}


@registry.register("schema_linker", "SpiderSchemaLinker")
class SpiderSchemaLinker(AbstractSchemaLinker):
    def __init__(
        self,
        tokenizer: dict,
        max_n_gram: int = 5,
        with_stemming: bool = False,
        blocking_match: bool = True,
        whole_entry_db_content_confidence: str = "high",
        partial_entry_db_content_confidence: str = "low",
    ):
        super(SpiderSchemaLinker, self).__init__()
        self.max_n_gram = max_n_gram
        self.with_stemming = with_stemming
        self.blocking_match = blocking_match
        self.whole_entry_db_content_confidence = MATCH_CONFIDENCE[
            whole_entry_db_content_confidence
        ]
        self.partial_entry_db_content_confidence = MATCH_CONFIDENCE[
            partial_entry_db_content_confidence
        ]
        self.tokenizer: AbstractTokenizer = registry.construct("tokenizer", tokenizer)

    def question_to_slml(self, question: str, sql_schema: SQLSchema,) -> str:
        tagged_question_tokens = tag_question_with_schema_links(
            tokenized_question=self.tokenizer.tokenize_with_raw(question),
            sql_schema=sql_schema,
            tokenize=self.tokenizer.tokenize,
            max_n_gram=self.max_n_gram,
            with_stemming=self.with_stemming,
            blocking_match=self.blocking_match,
            whole_entry_db_content_confidence=self.whole_entry_db_content_confidence,
            partial_entry_db_content_confidence=self.partial_entry_db_content_confidence,
        )
        slml_builder = SLMLBuilder(
            sql_schema=sql_schema, detokenize=self.tokenizer.detokenize
        )
        slml_builder.add_question_tokens(question_tokens=tagged_question_tokens)
        slml_question = slml_builder.build()
        return slml_question


def tag_question_with_schema_links(
    tokenized_question: Iterable[Tuple[str, str]],
    sql_schema: SQLSchema,
    tokenize: Callable[[str], Sequence[str]],
    max_n_gram: int,
    with_stemming: bool,
    blocking_match: bool,
    whole_entry_db_content_confidence: Optional[MatchConfidence],
    partial_entry_db_content_confidence: Optional[MatchConfidence],
) -> TaggedSequence:
    """

    :param tokenized_question:
    :param sql_schema:
    :param tokenize:
    :param max_n_gram:
    :param with_stemming:
    :param blocking_match:
    :param whole_entry_db_content_confidence:
    :param partial_entry_db_content_confidence:
    :return:
    """

    def _entry_type_to_confidence(entry_type):
        if entry_type is EntryType.WHOLE_ENTRY:
            return whole_entry_db_content_confidence
        else:
            return partial_entry_db_content_confidence

    # init BIO tags
    tagged_question_tokens = [
        TaggedToken(value=token, raw_value=raw_token, tag=OUTSIDE, match_tags=deque())
        for token, raw_token in tokenized_question
    ]
    # counter for column_name column_value table_name
    match_tags_counter = [[0,0,0] for i in range(len(tagged_question_tokens))]

    for n in range(max_n_gram, 0, -1):
        for (start, end), question_n_gram in get_spans(
            tagged_sequence=tagged_question_tokens, n=n
        ):
         
            if n == 1 and question_n_gram[0].value in stop_words:
               # print('pass stop words:', question_n_gram[0].value)
                continue 
                
            # Try to match column names
            for column_id, column_name in sql_schema.column_names.items():
                if (
                    column_id
                    not in sql_schema.column_to_table
                    # or sql_schema.column_to_table[column_id] is None
                ):
                    continue
                table_id = sql_schema.column_to_table[column_id]
                match = span_matches_entity(
                    tagged_span=question_n_gram,
                    entity_name=column_name,
                    tokenize=tokenize,
                    with_stemming=with_stemming,
                )

                # Try to match using db-content only if a column match did not succeed.
                # That means column matches have precedence!
                db_content_matches = []
                if match is NO_MATCH:
                    if table_id is not None:
                        db_content_matches = match_db_content(
                            [token.value for token in question_n_gram],
                            sql_schema.original_column_names[column_id],
                            sql_schema.original_table_names[table_id],
                            sql_schema.db_id,
                            sql_schema.db_path,
                            with_stemming=with_stemming,
                        )
                        # Filter non-None confidence.
                        db_content_matches = [
                            entry
                            for entry in db_content_matches
                            if _entry_type_to_confidence(entry[0]) is not None
                        ]
                        # Tag the sequence if a match was found
                        if db_content_matches:
                            match = VALUE_MATCH

                # Tag the sequence if a match was found
                if match is not NO_MATCH:
                    # Block the sequence
                    if blocking_match:
                        set_tags(
                            tagged_sequence=tagged_question_tokens, start=start, end=end
                        )
                    span = ''
                    match_values = ''
                    for idx in range(start, end):
                        if match is VALUE_MATCH:
                            # Only keep the match with the highest confidence
                            entry_type, match_value = max(
                                db_content_matches,
                                key=lambda match: _entry_type_to_confidence(match[0])
                            )
                            match_tag = ValueMatchTag(
                                confidence=_entry_type_to_confidence(entry_type),
                                column_id=column_id,
                                table_id=table_id,
                                value=match_value,
                            )
                            tagged_question_tokens[idx].match_tags.append(match_tag)
                            match_tags_counter[idx][1] += 1
                            match_values += ' ' + match_value
                        else:
                            match_tag = ColumnMatchTag(
                                confidence=(
                                    HighConfidenceMatch()
                                    if match == EXACT_MATCH
                                    else LowConfidenceMatch()
                                ),
                                column_id=column_id,
                                table_id=table_id,
                            )
                            tagged_question_tokens[idx].match_tags.append(match_tag)
                            match_tags_counter[idx][0] += 1
                        span+=" "+tagged_question_tokens[idx].value
                    # TODO just log
                    with open('link.log', 'a') as f:
                        if match is VALUE_MATCH:
                            f.write(
                                f'column-{match}: {n}-gram:{span}, column_name:{column_name}, value:{match_values}' + '\n')
                        else:
                            f.write(f'column-{match}: {n}-gram:{span}, column_name:{column_name}' + '\n')
    # reset BIO tags
    tagged_question_tokens: TaggedSequence = [
        replace(t, tag=OUTSIDE) for t in tagged_question_tokens
    ]

    for n in range(max_n_gram, 0, -1):
        for (start, end), question_n_gram in get_spans(
            tagged_sequence=tagged_question_tokens, n=n
        ):

            if n == 1 and question_n_gram[0].value in stop_words:
               # print('pass stop words:', question_n_gram[0].value)
                continue 
            # Try to match table names
            for table_id, table_name in sql_schema.table_names.items():
                match = span_matches_entity(
                    tagged_span=question_n_gram,
                    entity_name=table_name,
                    tokenize=tokenize,
                    with_stemming=with_stemming,
                )

                # Tag the sequence if a match was found
                if match is not NO_MATCH:
                    # Block the sequence
                    if blocking_match:
                        set_tags(
                            tagged_sequence=tagged_question_tokens, start=start, end=end
                        )
                    span = ''
                    for idx in range(start, end):
                        tagged_question_tokens[idx].match_tags.append(
                            TableMatchTag(
                                confidence=(
                                    HighConfidenceMatch()
                                    if match == EXACT_MATCH
                                    else LowConfidenceMatch()
                                ),
                                table_id=table_id,
                            )
                        )
                        match_tags_counter[idx][2] += 1
                        span+=" "+tagged_question_tokens[idx].value
                    # TODO just log
                    with open('link.log', 'a') as f:
                        f.write(f'table-{match}: {n}-gram:{span}, table_name:{table_name}'+'\n')
    # filter
    # for idx, tagged_token in enumerate(tagged_question_tokens):
    #     KEEP_COLUMN_NAME = match_tags_counter[idx][0] <= 3
    #     KEEP_COLUMN_VALUE = match_tags_counter[idx][1] <= 2
    #     KEEP_TABLE_NAME = match_tags_counter[idx][2] <= 2
    #     new_match_tags = deque()
    #     for match_tag in tagged_token.match_tags:
    #         if (type(match_tag) is ColumnMatchTag and KEEP_COLUMN_NAME) or \
    #                 (type(match_tag) is ValueMatchTag and KEEP_COLUMN_VALUE) or \
    #                 (type(match_tag) is TableMatchTag and KEEP_TABLE_NAME):
    #             new_match_tags.append(match_tag)
    #     tagged_token.match_tags = new_match_tags

    return tagged_question_tokens


BEGIN = "B"
INSIDE = "I"
OUTSIDE = "O"

EXACT_MATCH = "exact_match"
PARTIAL_MATCH = "partial_match"
VALUE_MATCH = "value_match"
NO_MATCH = None


def set_tags(tagged_sequence: TaggedSequence, start: int, end: int) -> None:
    if start < end:
        tagged_sequence[start].tag = BEGIN
    for idx in range(start + 1, end):
        tagged_sequence[idx].tag = INSIDE


def get_spans(
    tagged_sequence: TaggedSequence, n: int
) -> Generator[Tuple[Tuple[int, int], TaggedSequence], None, None]:
    """Generate untagged spans from sequence"""
    start = 0
    end = n
    while end <= len(tagged_sequence):
        # yield span only if not yet tagged
        if all(
            [tagged_token.tag == OUTSIDE for tagged_token in tagged_sequence[start:end]]
        ):
            yield (start, end), tagged_sequence[start:end]
        start += 1
        end += 1


def span_matches_entity(
    tagged_span: TaggedSequence,
    entity_name: str,
    tokenize: Callable[[str], Sequence[str]],
    with_stemming: bool,
) -> Optional[str]:
    """
    Check if span and entity match (modulo stemming if desired)
    """
    if with_stemming:
        span_seq = pre_process_words(
            [tagged_token.value for tagged_token in tagged_span],
            with_stemming=with_stemming,
        )
        entity_name_seq = pre_process_words(
            tokenize(entity_name), with_stemming=with_stemming
        )
        if span_seq == entity_name_seq:
            return EXACT_MATCH
        elif has_subsequence(seq=entity_name_seq, subseq=span_seq):
            return PARTIAL_MATCH
        else:
            return NO_MATCH
    else:
        span_str = " ".join([tagged_token.value for tagged_token in tagged_span])
        entity_name_str = entity_name
        if span_str == entity_name_str:
            return EXACT_MATCH
        # if span_str == entity_name_str or \
        #     (len(span_str.split(' ')) == 1 and len(entity_name_str.split(' ')) == 1 and
        #      similarity(stemmer.stem(span_str), stemmer.stem(entity_name_str)) > 0.68) or \
        #         (len(span_str.split(' ')) == len(entity_name_str.split(' ')) and
        #          similarity(stemmer.stem(span_str), stemmer.stem(entity_name_str)) > 0.9):
        #     return EXACT_MATCH
        elif span_str in entity_name_str:
            # if len(span_str)<2 and len(entity_name_str)-len(span_str)>5:
            #     return NO_MATCH
            # if len(span_str)<4 and len(entity_name_str)-len(span_str)>5  and len(entity_name_str.split(' '))==1:
            #     return NO_MATCH

            # filter with similarity
            if len(entity_name_str.split(' '))==1:
                if similarity(stemmer.stem(tagged_span[0].value), stemmer.stem(entity_name_str)):
                    return PARTIAL_MATCH if similarity(stemmer.stem(tagged_span[0].value), stemmer.stem(entity_name_str)) > 0.55 else NO_MATCH
                else:
                    return PARTIAL_MATCH if not(len(span_str)<3 and len(entity_name_str)-len(span_str)>3) else NO_MATCH
            else:
                return PARTIAL_MATCH if not(len(span_str)<3 and len(entity_name_str)-len(span_str)>5) else NO_MATCH
        elif len(tagged_span) == 1:
            if stemmer.stem(tagged_span[0].value) == entity_name_str:
                return EXACT_MATCH

            if stemmer.stem(tagged_span[0].value) in entity_name_str:
                return PARTIAL_MATCH if not(len(span_str)<3 and len(entity_name_str)-len(span_str)>5) else NO_MATCH

            if  entity_name_str in span_str:
                # When span length is 1, also test the other inclusion
                # filter
                if similarity(stemmer.stem(tagged_span[0].value), stemmer.stem(entity_name_str)):
                    return PARTIAL_MATCH if similarity(stemmer.stem(tagged_span[0].value), stemmer.stem(entity_name_str)) > 0.55 else NO_MATCH
                else:
                    return PARTIAL_MATCH if not (
                                len(span_str) < 3 and len(entity_name_str) - len(span_str) > 3) else NO_MATCH
        else:
            return NO_MATCH
