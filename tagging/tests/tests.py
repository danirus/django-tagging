# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import six

from django import forms
from django.db.models import Q
from django.test import TestCase
from tagging.forms import TagField
from tagging import settings
from tagging.models import Tag, TaggedItem
from tagging.tests.models import Article, Link, Perch, Parrot, FormTest, FormTestNull
from tagging.utils import calculate_cloud, edit_string_for_tags, get_tag_list, get_tag, parse_tag_input
from tagging.utils import LINEAR

#############
# Utilities #
#############

class TestParseTagInput(TestCase):
    def test_with_simple_space_delimited_tags(self):
        """ Test with simple space-delimited tags. """
        
        self.assertEqual(parse_tag_input('one'), ['one'])
        self.assertEqual(parse_tag_input('one two'), ['one', 'two'])
        self.assertEqual(parse_tag_input('one two three'), ['one', 'three', 'two'])
        self.assertEqual(parse_tag_input('one one two two'), ['one', 'two'])
    
    def test_with_comma_delimited_multiple_words(self):
        """ Test with comma-delimited multiple words.
            An unquoted comma in the input will trigger this. """
            
        self.assertEqual(parse_tag_input(',one'), ['one'])
        self.assertEqual(parse_tag_input(',one two'), ['one two'])
        self.assertEqual(parse_tag_input(',one two three'), ['one two three'])
        self.assertEqual(parse_tag_input('a-one, a-two and a-three'),
            ['a-one', 'a-two and a-three'])
    
    def test_with_double_quoted_multiple_words(self):
        """ Test with double-quoted multiple words.
            A completed quote will trigger this.  Unclosed quotes are ignored. """
            
        self.assertEqual(parse_tag_input('"one'), ['one'])
        self.assertEqual(parse_tag_input('"one two'), ['one', 'two'])
        self.assertEqual(parse_tag_input('"one two three'), ['one', 'three', 'two'])
        self.assertEqual(parse_tag_input('"one two"'), ['one two'])
        self.assertEqual(parse_tag_input('a-one "a-two and a-three"'),
            ['a-one', 'a-two and a-three'])
    
    def test_with_no_loose_commas(self):
        """ Test with no loose commas -- split on spaces. """
        self.assertEqual(parse_tag_input('one two "thr,ee"'), ['one', 'thr,ee', 'two'])
        
    def test_with_loose_commas(self):
        """ Loose commas - split on commas """
        self.assertEqual(parse_tag_input('"one", two three'), ['one', 'two three'])
        
    def test_tags_with_double_quotes_can_contain_commas(self):
        """ Double quotes can contain commas """
        self.assertEqual(parse_tag_input('a-one "a-two, and a-three"'),
            ['a-one', 'a-two, and a-three'])
        self.assertEqual(parse_tag_input('"two", one, one, two, "one"'),
            ['one', 'two'])
    
    def test_with_naughty_input(self):
        """ Test with naughty input. """
        
        # Bad users! Naughty users!
        self.assertEqual(parse_tag_input(None), [])
        self.assertEqual(parse_tag_input(''), [])
        self.assertEqual(parse_tag_input('"'), [])
        self.assertEqual(parse_tag_input('""'), [])
        self.assertEqual(parse_tag_input('"' * 7), [])
        self.assertEqual(parse_tag_input(',,,,,,'), [])
        self.assertEqual(parse_tag_input('",",",",",",","'), [','])
        self.assertEqual(parse_tag_input('a-one "a-two" and "a-three'),
            ['a-one', 'a-three', 'a-two', 'and'])
        
class TestNormalisedTagListInput(TestCase):
    def setUp(self):
        self.cheese = Tag.objects.create(name='cheese')
        self.toast = Tag.objects.create(name='toast')
        
    def test_single_tag_object_as_input(self):
        self.assertEqual(get_tag_list(self.cheese), [self.cheese])
    
    def test_space_delimeted_string_as_input(self):
        ret = get_tag_list('cheese toast')
        self.assertEqual(len(ret), 2)
        self.assertTrue(self.cheese in ret)
        self.assertTrue(self.toast in ret)
        
    def test_comma_delimeted_string_as_input(self):
        ret = get_tag_list('cheese,toast')
        self.assertEqual(len(ret), 2)
        self.assertTrue(self.cheese in ret)
        self.assertTrue(self.toast in ret)
    
    def test_with_empty_list(self):
        self.assertEqual(get_tag_list([]), [])
    
    def test_list_of_two_strings(self):
        ret = get_tag_list(['cheese', 'toast'])
        self.assertEqual(len(ret), 2)
        self.assertTrue(self.cheese in ret)
        self.assertTrue(self.toast in ret)
    
    def test_list_of_tag_primary_keys(self):
        ret = get_tag_list([self.cheese.id, self.toast.id])
        self.assertEqual(len(ret), 2)
        self.assertTrue(self.cheese in ret)
        self.assertTrue(self.toast in ret)
    
    def test_list_of_strings_with_strange_nontag_string(self):
        ret = get_tag_list(['cheese', 'toast', 'ŠĐĆŽćžšđ'])
        self.assertEqual(len(ret), 2)
        self.assertTrue(self.cheese in ret)
        self.assertTrue(self.toast in ret)
    
    def test_list_of_tag_instances(self):
        ret = get_tag_list([self.cheese, self.toast])
        self.assertEqual(len(ret), 2)
        self.assertTrue(self.cheese in ret)
        self.assertTrue(self.toast in ret)
    
    def test_tuple_of_instances(self):
        ret = get_tag_list((self.cheese, self.toast))
        self.assertEqual(len(ret), 2)
        self.assertTrue(self.cheese in ret)
        self.assertTrue(self.toast in ret)
    
    def test_with_tag_filter(self):
        ret = get_tag_list(Tag.objects.filter(name__in=['cheese', 'toast']))
        self.assertEqual(len(ret), 2)
        self.assertTrue(self.cheese in ret)
        self.assertTrue(self.toast in ret)
        
    def test_with_invalid_input_mix_of_string_and_instance(self):
        try:
            get_tag_list(['cheese', self.toast])
        except ValueError as exc:
            self.assertEqual(str(exc),
                'If a list or tuple of tags is provided, they must all be tag names, Tag objects or Tag ids.')
        except Exception as exc:
            raise self.failureException('the wrong type of exception was raised: type [%s] value [%]' %\
                (str(type(exc)), str(exc)))
        else:
            raise self.failureException('a ValueError exception was supposed to be raised!')
    
    def test_with_invalid_input(self):
        try:
            get_tag_list(29)
        except ValueError as exc:
            self.assertEqual(str(exc), 'The tag input given was invalid.')
        except Exception as exc:
            raise self.failureException('the wrong type of exception was raised: type [%s] value [%s]' %\
                (str(type(exc)), str(exc)))
        else:
            raise self.failureException('a ValueError exception was supposed to be raised!')

    def test_with_tag_instance(self):
        self.assertEqual(get_tag(self.cheese), self.cheese)
    
    def test_with_string(self):
        self.assertEqual(get_tag('cheese'), self.cheese)
    
    def test_with_primary_key(self):
        self.assertEqual(get_tag(self.cheese.id), self.cheese)
    
    def test_nonexistent_tag(self):
        self.assertEqual(get_tag('mouse'), None)

class TestCalculateCloud(TestCase):
    def setUp(self):
        self.tags = []
        for line in open(os.path.join(os.path.dirname(__file__), 'tags.txt')).readlines():
            name, count = line.rstrip().split()
            tag = Tag(name=name)
            tag.count = int(count)
            self.tags.append(tag)
    
    def test_default_distribution(self):
        sizes = {}
        for tag in calculate_cloud(self.tags, steps=5):
            sizes[tag.font_size] = sizes.get(tag.font_size, 0) + 1
        
        # This isn't a pre-calculated test, just making sure it's consistent
        self.assertEqual(sizes[1], 48)
        self.assertEqual(sizes[2], 30)
        self.assertEqual(sizes[3], 19)
        self.assertEqual(sizes[4], 15)
        self.assertEqual(sizes[5], 10)
    
    def test_linear_distribution(self):
        sizes = {}
        for tag in calculate_cloud(self.tags, steps=5, distribution=LINEAR):
            sizes[tag.font_size] = sizes.get(tag.font_size, 0) + 1
        
        # This isn't a pre-calculated test, just making sure it's consistent
        self.assertEqual(sizes[1], 97)
        self.assertEqual(sizes[2], 12)
        self.assertEqual(sizes[3], 7)
        self.assertEqual(sizes[4], 2)
        self.assertEqual(sizes[5], 4)
    
    def test_invalid_distribution(self):
        try:
            calculate_cloud(self.tags, steps=5, distribution='cheese')
        except ValueError as exc:
            self.assertEqual(str(exc), 'Invalid distribution algorithm specified: cheese.')
        except Exception as exc:
            raise self.failureException('the wrong type of exception was raised: type [%s] value [%s]' %\
                (str(type(exc)), str(exc)))
        else:
            raise self.failureException('a ValueError exception was supposed to be raised!')
        
###########
# Tagging #
###########

class TestBasicTagging(TestCase):
    def setUp(self):
        self.dead_parrot = Parrot.objects.create(state='dead')
    
    def test_update_tags(self):
        Tag.objects.update_tags(self.dead_parrot, 'foo,bar,"ter"')
        tags = Tag.objects.get_for_object(self.dead_parrot)
        self.assertEqual(len(tags), 3)
        self.assertTrue(get_tag('foo') in tags)
        self.assertTrue(get_tag('bar') in tags)
        self.assertTrue(get_tag('ter') in tags)
        
        Tag.objects.update_tags(self.dead_parrot, '"foo" bar "baz"')
        tags = Tag.objects.get_for_object(self.dead_parrot)
        self.assertEqual(len(tags), 3)
        self.assertTrue(get_tag('bar') in tags)
        self.assertTrue(get_tag('baz') in tags)
        self.assertTrue(get_tag('foo') in tags)
    
    def test_add_tag(self):
        # start off in a known, mildly interesting state
        Tag.objects.update_tags(self.dead_parrot, 'foo bar baz')
        tags = Tag.objects.get_for_object(self.dead_parrot)
        self.assertEqual(len(tags), 3)
        self.assertTrue(get_tag('bar') in tags)
        self.assertTrue(get_tag('baz') in tags)
        self.assertTrue(get_tag('foo') in tags)
        
        # try to add a tag that already exists
        Tag.objects.add_tag(self.dead_parrot, 'foo')
        tags = Tag.objects.get_for_object(self.dead_parrot)
        self.assertEqual(len(tags), 3)
        self.assertTrue(get_tag('bar') in tags)
        self.assertTrue(get_tag('baz') in tags)
        self.assertTrue(get_tag('foo') in tags)
        
        # now add a tag that doesn't already exist
        Tag.objects.add_tag(self.dead_parrot, 'zip')
        tags = Tag.objects.get_for_object(self.dead_parrot)
        self.assertEqual(len(tags), 4)
        self.assertTrue(get_tag('zip') in tags)
        self.assertTrue(get_tag('bar') in tags)
        self.assertTrue(get_tag('baz') in tags)
        self.assertTrue(get_tag('foo') in tags)
    
    def test_add_tag_invalid_input_no_tags_specified(self):
        # start off in a known, mildly interesting state
        Tag.objects.update_tags(self.dead_parrot, 'foo bar baz')
        tags = Tag.objects.get_for_object(self.dead_parrot)
        self.assertEqual(len(tags), 3)
        self.assertTrue(get_tag('bar') in tags)
        self.assertTrue(get_tag('baz') in tags)
        self.assertTrue(get_tag('foo') in tags)
        
        try:
            Tag.objects.add_tag(self.dead_parrot, '    ')
        except AttributeError as exc:
            self.assertEqual(str(exc), 'No tags were given: "    ".')
        except Exception as exc:
            raise self.failureException('the wrong type of exception was raised: type [%s] value [%s]' %\
                (str(type(exc)), str(exc)))
        else:
            raise self.failureException('an AttributeError exception was supposed to be raised!')
        
    def test_add_tag_invalid_input_multiple_tags_specified(self):
        # start off in a known, mildly interesting state
        Tag.objects.update_tags(self.dead_parrot, 'foo bar baz')
        tags = Tag.objects.get_for_object(self.dead_parrot)
        self.assertEqual(len(tags), 3)
        self.assertTrue(get_tag('bar') in tags)
        self.assertTrue(get_tag('baz') in tags)
        self.assertTrue(get_tag('foo') in tags)
        
        try:
            Tag.objects.add_tag(self.dead_parrot, 'one two')
        except AttributeError as exc:
            self.assertEqual(str(exc), 'Multiple tags were given: "one two".')
        except Exception as exc:
            raise self.failureException('the wrong type of exception was raised: type [%s] value [%s]' %\
                (str(type(exc)), str(exc)))
        else:
            raise self.failureException('an AttributeError exception was supposed to be raised!')
    
    def test_update_tags_exotic_characters(self):
        # start off in a known, mildly interesting state
        Tag.objects.update_tags(self.dead_parrot, 'foo bar baz')
        tags = Tag.objects.get_for_object(self.dead_parrot)
        self.assertEqual(len(tags), 3)
        self.assertTrue(get_tag('bar') in tags)
        self.assertTrue(get_tag('baz') in tags)
        self.assertTrue(get_tag('foo') in tags)
        
        Tag.objects.update_tags(self.dead_parrot, 'ŠĐĆŽćžšđ')
        tags = Tag.objects.get_for_object(self.dead_parrot)
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0].name, 'ŠĐĆŽćžšđ')
        
        Tag.objects.update_tags(self.dead_parrot, '你好')
        tags = Tag.objects.get_for_object(self.dead_parrot)
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0].name, '你好')
    
    def test_update_tags_with_none(self):
        # start off in a known, mildly interesting state
        Tag.objects.update_tags(self.dead_parrot, 'foo bar baz')
        tags = Tag.objects.get_for_object(self.dead_parrot)
        self.assertEqual(len(tags), 3)
        self.assertTrue(get_tag('bar') in tags)
        self.assertTrue(get_tag('baz') in tags)
        self.assertTrue(get_tag('foo') in tags)
        
        Tag.objects.update_tags(self.dead_parrot, None)
        tags = Tag.objects.get_for_object(self.dead_parrot)
        self.assertEqual(len(tags), 0)

class TestModelTagField(TestCase):
    """ Test the 'tags' field on models. """
    
    def test_create_with_tags_specified(self):
        f1 = FormTest.objects.create(tags='test3 test2 test1')
        tags = Tag.objects.get_for_object(f1)
        test1_tag = get_tag('test1')
        test2_tag = get_tag('test2')
        test3_tag = get_tag('test3')
        self.assertTrue(None not in (test1_tag, test2_tag, test3_tag))
        self.assertEqual(len(tags), 3)
        self.assertTrue(test1_tag in tags)
        self.assertTrue(test2_tag in tags)
        self.assertTrue(test3_tag in tags)
    
    def test_update_via_tags_field(self):
        f1 = FormTest.objects.create(tags='test3 test2 test1')
        tags = Tag.objects.get_for_object(f1)
        test1_tag = get_tag('test1')
        test2_tag = get_tag('test2')
        test3_tag = get_tag('test3')
        self.assertTrue(None not in (test1_tag, test2_tag, test3_tag))
        self.assertEqual(len(tags), 3)
        self.assertTrue(test1_tag in tags)
        self.assertTrue(test2_tag in tags)
        self.assertTrue(test3_tag in tags)
        
        f1.tags = 'test4'
        f1.save()
        tags = Tag.objects.get_for_object(f1)
        test4_tag = get_tag('test4')
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0], test4_tag)
        
        f1.tags = ''
        f1.save()
        tags = Tag.objects.get_for_object(f1)
        self.assertEqual(len(tags), 0)

    def test_update_via_tags(self):
        f1 = FormTest.objects.create(tags='one two three')
        Tag.objects.get(name='three').delete()
        t2 = Tag.objects.get(name='two')
        t2.name = 'new'
        t2.save()
        f1again = FormTest.objects.get(pk=f1.pk)
        self.failIf('three' in f1again.tags)
        self.failIf('two' in f1again.tags)
        self.assertTrue('new' in f1again.tags)

    def test_creation_without_specifying_tags(self):
        f1 = FormTest()
        self.assertEqual(f1.tags, '')

    def test_creation_with_nullable_tags_field(self):
        f1 = FormTestNull()
        self.assertEqual(f1.tags, '')
        
class TestSettings(TestCase):
    def setUp(self):
        self.original_force_lower_case_tags = settings.FORCE_LOWERCASE_TAGS
        self.dead_parrot = Parrot.objects.create(state='dead')
    
    def tearDown(self):
        settings.FORCE_LOWERCASE_TAGS = self.original_force_lower_case_tags
    
    def test_force_lowercase_tags(self):
        """ Test forcing tags to lowercase. """
        
        settings.FORCE_LOWERCASE_TAGS = True
        
        Tag.objects.update_tags(self.dead_parrot, 'foO bAr Ter')
        tags = Tag.objects.get_for_object(self.dead_parrot)
        self.assertEqual(len(tags), 3)
        foo_tag = get_tag('foo')
        bar_tag = get_tag('bar')
        ter_tag = get_tag('ter')
        self.assertTrue(foo_tag in tags)
        self.assertTrue(bar_tag in tags)
        self.assertTrue(ter_tag in tags)
        
        Tag.objects.update_tags(self.dead_parrot, 'foO bAr baZ')
        tags = Tag.objects.get_for_object(self.dead_parrot)
        baz_tag = get_tag('baz')
        self.assertEqual(len(tags), 3)
        self.assertTrue(bar_tag in tags)
        self.assertTrue(baz_tag in tags)
        self.assertTrue(foo_tag in tags)
        
        Tag.objects.add_tag(self.dead_parrot, 'FOO')
        tags = Tag.objects.get_for_object(self.dead_parrot)
        self.assertEqual(len(tags), 3)
        self.assertTrue(bar_tag in tags)
        self.assertTrue(baz_tag in tags)
        self.assertTrue(foo_tag in tags)
        
        Tag.objects.add_tag(self.dead_parrot, 'Zip')
        tags = Tag.objects.get_for_object(self.dead_parrot)
        self.assertEqual(len(tags), 4)
        zip_tag = get_tag('zip')
        self.assertTrue(bar_tag in tags)
        self.assertTrue(baz_tag in tags)
        self.assertTrue(foo_tag in tags)
        self.assertTrue(zip_tag in tags)
        
        f1 = FormTest.objects.create()
        f1.tags = 'TEST5'
        f1.save()
        tags = Tag.objects.get_for_object(f1)
        test5_tag = get_tag('test5')
        self.assertEqual(len(tags), 1)
        self.assertTrue(test5_tag in tags)
        self.assertEqual(f1.tags, 'test5')

class TestTagUsageForModelBaseCase(TestCase):
    def test_tag_usage_for_model_empty(self):
        self.assertEqual(Tag.objects.usage_for_model(Parrot), [])

class TestTagUsageForModel(TestCase):
    def setUp(self):
        parrot_details = (
            ('pining for the fjords', 9, True,  'foo bar'),
            ('passed on',             6, False, 'bar baz ter'),
            ('no more',               4, True,  'foo ter'),
            ('late',                  2, False, 'bar ter'),
        )
        
        for state, perch_size, perch_smelly, tags in parrot_details:
            perch = Perch.objects.create(size=perch_size, smelly=perch_smelly)
            parrot = Parrot.objects.create(state=state, perch=perch)
            Tag.objects.update_tags(parrot, tags)
    
    def test_tag_usage_for_model(self):
        tag_usage = Tag.objects.usage_for_model(Parrot, counts=True)
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 4)
        self.assertTrue(('bar', 3) in relevant_attribute_list)
        self.assertTrue(('baz', 1) in relevant_attribute_list)
        self.assertTrue(('foo', 2) in relevant_attribute_list)
        self.assertTrue(('ter', 3) in relevant_attribute_list)
    
    def test_tag_usage_for_model_with_min_count(self):
        tag_usage = Tag.objects.usage_for_model(Parrot, min_count = 2)
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 3)
        self.assertTrue(('bar', 3) in relevant_attribute_list)
        self.assertTrue(('foo', 2) in relevant_attribute_list)
        self.assertTrue(('ter', 3) in relevant_attribute_list)
    
    def test_tag_usage_with_filter_on_model_objects(self):
        tag_usage = Tag.objects.usage_for_model(Parrot, counts=True, filters=dict(state='no more'))
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 2)
        self.assertTrue(('foo', 1) in relevant_attribute_list)
        self.assertTrue(('ter', 1) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_model(Parrot, counts=True, filters=dict(state__startswith='p'))
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 4)
        self.assertTrue(('bar', 2) in relevant_attribute_list)
        self.assertTrue(('baz', 1) in relevant_attribute_list)
        self.assertTrue(('foo', 1) in relevant_attribute_list)
        self.assertTrue(('ter', 1) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_model(Parrot, counts=True, filters=dict(perch__size__gt=4))
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 4)
        self.assertTrue(('bar', 2) in relevant_attribute_list)
        self.assertTrue(('baz', 1) in relevant_attribute_list)
        self.assertTrue(('foo', 1) in relevant_attribute_list)
        self.assertTrue(('ter', 1) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_model(Parrot, counts=True, filters=dict(perch__smelly=True))
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 3)
        self.assertTrue(('bar', 1) in relevant_attribute_list)
        self.assertTrue(('foo', 2) in relevant_attribute_list)
        self.assertTrue(('ter', 1) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_model(Parrot, min_count=2, filters=dict(perch__smelly=True))
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 1)
        self.assertTrue(('foo', 2) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_model(Parrot, filters=dict(perch__size__gt=4))
        relevant_attribute_list = [(tag.name, hasattr(tag, 'counts')) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 4)
        self.assertTrue(('bar', False) in relevant_attribute_list)
        self.assertTrue(('baz', False) in relevant_attribute_list)
        self.assertTrue(('foo', False) in relevant_attribute_list)
        self.assertTrue(('ter', False) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_model(Parrot, filters=dict(perch__size__gt=99))
        relevant_attribute_list = [(tag.name, hasattr(tag, 'counts')) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 0)

class TestTagsRelatedForModel(TestCase):
    def setUp(self):
        parrot_details = (
            ('pining for the fjords', 9, True,  'foo bar'),
            ('passed on',             6, False, 'bar baz ter'),
            ('no more',               4, True,  'foo ter'),
            ('late',                  2, False, 'bar ter'),
        )
        
        for state, perch_size, perch_smelly, tags in parrot_details:
            perch = Perch.objects.create(size=perch_size, smelly=perch_smelly)
            parrot = Parrot.objects.create(state=state, perch=perch)
            Tag.objects.update_tags(parrot, tags)
            
    def test_related_for_model_with_tag_query_sets_as_input(self):
        related_tags = Tag.objects.related_for_model(Tag.objects.filter(name__in=['bar']), Parrot, counts=True)
        relevant_attribute_list = [(tag.name, tag.count) for tag in related_tags]
        self.assertEqual(len(relevant_attribute_list), 3)
        self.assertTrue(('baz', 1) in relevant_attribute_list)
        self.assertTrue(('foo', 1) in relevant_attribute_list)
        self.assertTrue(('ter', 2) in relevant_attribute_list)
        
        related_tags = Tag.objects.related_for_model(Tag.objects.filter(name__in=['bar']), Parrot, min_count=2)
        relevant_attribute_list = [(tag.name, tag.count) for tag in related_tags]
        self.assertEqual(len(relevant_attribute_list), 1)
        self.assertTrue(('ter', 2) in relevant_attribute_list)
        
        related_tags = Tag.objects.related_for_model(Tag.objects.filter(name__in=['bar']), Parrot, counts=False)
        relevant_attribute_list = [tag.name for tag in related_tags]
        self.assertEqual(len(relevant_attribute_list), 3)
        self.assertTrue('baz' in relevant_attribute_list)
        self.assertTrue('foo' in relevant_attribute_list)
        self.assertTrue('ter' in relevant_attribute_list)
        
        related_tags = Tag.objects.related_for_model(Tag.objects.filter(name__in=['bar', 'ter']), Parrot, counts=True)
        relevant_attribute_list = [(tag.name, tag.count) for tag in related_tags]
        self.assertEqual(len(relevant_attribute_list), 1)
        self.assertTrue(('baz', 1) in relevant_attribute_list)
        
        related_tags = Tag.objects.related_for_model(Tag.objects.filter(name__in=['bar', 'ter', 'baz']), Parrot, counts=True)
        relevant_attribute_list = [(tag.name, tag.count) for tag in related_tags]
        self.assertEqual(len(relevant_attribute_list), 0)
        
    def test_related_for_model_with_tag_strings_as_input(self):
        # Once again, with feeling (strings)
        related_tags = Tag.objects.related_for_model('bar', Parrot, counts=True)
        relevant_attribute_list = [(tag.name, tag.count) for tag in related_tags]
        self.assertEqual(len(relevant_attribute_list), 3)
        self.assertTrue(('baz', 1) in relevant_attribute_list)
        self.assertTrue(('foo', 1) in relevant_attribute_list)
        self.assertTrue(('ter', 2) in relevant_attribute_list)
        
        related_tags = Tag.objects.related_for_model('bar', Parrot, min_count=2)
        relevant_attribute_list = [(tag.name, tag.count) for tag in related_tags]
        self.assertEqual(len(relevant_attribute_list), 1)
        self.assertTrue(('ter', 2) in relevant_attribute_list)
        
        related_tags = Tag.objects.related_for_model('bar', Parrot, counts=False)
        relevant_attribute_list = [tag.name for tag in related_tags]
        self.assertEqual(len(relevant_attribute_list), 3)
        self.assertTrue('baz' in relevant_attribute_list)
        self.assertTrue('foo' in relevant_attribute_list)
        self.assertTrue('ter' in relevant_attribute_list)
        
        related_tags = Tag.objects.related_for_model(['bar', 'ter'], Parrot, counts=True)
        relevant_attribute_list = [(tag.name, tag.count) for tag in related_tags]
        self.assertEqual(len(relevant_attribute_list), 1)
        self.assertTrue(('baz', 1) in relevant_attribute_list)
        
        related_tags = Tag.objects.related_for_model(['bar', 'ter', 'baz'], Parrot, counts=True)
        relevant_attribute_list = [(tag.name, tag.count) for tag in related_tags]
        self.assertEqual(len(relevant_attribute_list), 0)
        
class TestGetTaggedObjectsByModel(TestCase):
    def setUp(self):
        parrot_details = (
            ('pining for the fjords', 9, True,  'foo bar'),
            ('passed on',             6, False, 'bar baz ter'),
            ('no more',               4, True,  'foo ter'),
            ('late',                  2, False, 'bar ter'),
        )
        
        for state, perch_size, perch_smelly, tags in parrot_details:
            perch = Perch.objects.create(size=perch_size, smelly=perch_smelly)
            parrot = Parrot.objects.create(state=state, perch=perch)
            Tag.objects.update_tags(parrot, tags)
            
        self.foo = Tag.objects.get(name='foo')
        self.bar = Tag.objects.get(name='bar')
        self.baz = Tag.objects.get(name='baz')
        self.ter = Tag.objects.get(name='ter')
        
        self.pining_for_the_fjords_parrot = Parrot.objects.get(state='pining for the fjords')
        self.passed_on_parrot = Parrot.objects.get(state='passed on')
        self.no_more_parrot = Parrot.objects.get(state='no more')
        self.late_parrot = Parrot.objects.get(state='late')
        
    def test_get_by_model_simple(self):
        parrots = TaggedItem.objects.get_by_model(Parrot, self.foo)
        self.assertEqual(len(parrots), 2)
        self.assertTrue(self.no_more_parrot in parrots)
        self.assertTrue(self.pining_for_the_fjords_parrot in parrots)
        
        parrots = TaggedItem.objects.get_by_model(Parrot, self.bar)
        self.assertEqual(len(parrots), 3)
        self.assertTrue(self.late_parrot in parrots)
        self.assertTrue(self.passed_on_parrot in parrots)
        self.assertTrue(self.pining_for_the_fjords_parrot in parrots)
    
    def test_get_by_model_intersection(self):
        parrots = TaggedItem.objects.get_by_model(Parrot, [self.foo, self.baz])
        self.assertEqual(len(parrots), 0)
        
        parrots = TaggedItem.objects.get_by_model(Parrot, [self.foo, self.bar])
        self.assertEqual(len(parrots), 1)
        self.assertTrue(self.pining_for_the_fjords_parrot in parrots)
        
        parrots = TaggedItem.objects.get_by_model(Parrot, [self.bar, self.ter])
        self.assertEqual(len(parrots), 2)
        self.assertTrue(self.late_parrot in parrots)
        self.assertTrue(self.passed_on_parrot in parrots)
        
        # Issue 114 - Intersection with non-existant tags
        parrots = TaggedItem.objects.get_intersection_by_model(Parrot, [])
        self.assertEqual(len(parrots), 0)
    
    def test_get_by_model_with_tag_querysets_as_input(self):
        parrots = TaggedItem.objects.get_by_model(Parrot, Tag.objects.filter(name__in=['foo', 'baz']))
        self.assertEqual(len(parrots), 0)
        
        parrots = TaggedItem.objects.get_by_model(Parrot, Tag.objects.filter(name__in=['foo', 'bar']))
        self.assertEqual(len(parrots), 1)
        self.assertTrue(self.pining_for_the_fjords_parrot in parrots)
        
        parrots = TaggedItem.objects.get_by_model(Parrot, Tag.objects.filter(name__in=['bar', 'ter']))
        self.assertEqual(len(parrots), 2)
        self.assertTrue(self.late_parrot in parrots)
        self.assertTrue(self.passed_on_parrot in parrots)
    
    def test_get_by_model_with_strings_as_input(self):
        parrots = TaggedItem.objects.get_by_model(Parrot, 'foo baz')
        self.assertEqual(len(parrots), 0)
        
        parrots = TaggedItem.objects.get_by_model(Parrot, 'foo bar')
        self.assertEqual(len(parrots), 1)
        self.assertTrue(self.pining_for_the_fjords_parrot in parrots)
        
        parrots = TaggedItem.objects.get_by_model(Parrot, 'bar ter')
        self.assertEqual(len(parrots), 2)
        self.assertTrue(self.late_parrot in parrots)
        self.assertTrue(self.passed_on_parrot in parrots)
        
    def test_get_by_model_with_lists_of_strings_as_input(self):
        parrots = TaggedItem.objects.get_by_model(Parrot, ['foo', 'baz'])
        self.assertEqual(len(parrots), 0)
        
        parrots = TaggedItem.objects.get_by_model(Parrot, ['foo', 'bar'])
        self.assertEqual(len(parrots), 1)
        self.assertTrue(self.pining_for_the_fjords_parrot in parrots)
        
        parrots = TaggedItem.objects.get_by_model(Parrot, ['bar', 'ter'])
        self.assertEqual(len(parrots), 2)
        self.assertTrue(self.late_parrot in parrots)
        self.assertTrue(self.passed_on_parrot in parrots)
    
    def test_get_by_nonexistent_tag(self):
        # Issue 50 - Get by non-existent tag
        parrots = TaggedItem.objects.get_by_model(Parrot, 'argatrons')
        self.assertEqual(len(parrots), 0)
    
    def test_get_union_by_model(self):
        parrots = TaggedItem.objects.get_union_by_model(Parrot, ['foo', 'ter'])
        self.assertEqual(len(parrots), 4)
        self.assertTrue(self.late_parrot in parrots)
        self.assertTrue(self.no_more_parrot in parrots)
        self.assertTrue(self.passed_on_parrot in parrots)
        self.assertTrue(self.pining_for_the_fjords_parrot in parrots)
        
        parrots = TaggedItem.objects.get_union_by_model(Parrot, ['bar', 'baz'])
        self.assertEqual(len(parrots), 3)
        self.assertTrue(self.late_parrot in parrots)
        self.assertTrue(self.passed_on_parrot in parrots)
        self.assertTrue(self.pining_for_the_fjords_parrot in parrots)
        
        # Issue 114 - Union with non-existant tags
        parrots = TaggedItem.objects.get_union_by_model(Parrot, [])
        self.assertEqual(len(parrots), 0)

class TestGetRelatedTaggedItems(TestCase):
    def setUp(self):
        parrot_details = (
            ('pining for the fjords', 9, True,  'foo bar'),
            ('passed on',             6, False, 'bar baz ter'),
            ('no more',               4, True,  'foo ter'),
            ('late',                  2, False, 'bar ter'),
        )
        
        for state, perch_size, perch_smelly, tags in parrot_details:
            perch = Perch.objects.create(size=perch_size, smelly=perch_smelly)
            parrot = Parrot.objects.create(state=state, perch=perch)
            Tag.objects.update_tags(parrot, tags)
            
        self.l1 = Link.objects.create(name='link 1')
        Tag.objects.update_tags(self.l1, 'tag1 tag2 tag3 tag4 tag5')
        self.l2 = Link.objects.create(name='link 2')
        Tag.objects.update_tags(self.l2, 'tag1 tag2 tag3')
        self.l3 = Link.objects.create(name='link 3')
        Tag.objects.update_tags(self.l3, 'tag1')
        self.l4 = Link.objects.create(name='link 4')
        
        self.a1 = Article.objects.create(name='article 1')
        Tag.objects.update_tags(self.a1, 'tag1 tag2 tag3 tag4')
    
    def test_get_related_objects_of_same_model(self):
        related_objects = TaggedItem.objects.get_related(self.l1, Link)
        self.assertEqual(len(related_objects), 2)
        self.assertTrue(self.l2 in related_objects)
        self.assertTrue(self.l3 in related_objects)
        
        related_objects = TaggedItem.objects.get_related(self.l4, Link)
        self.assertEqual(len(related_objects), 0)
    
    def test_get_related_objects_of_same_model_limited_number_of_results(self):
        # This fails on Oracle because it has no support for a 'LIMIT' clause.
        # See http://asktom.oracle.com/pls/asktom/f?p=100:11:0::::P11_QUESTION_ID:127412348064
        
        # ask for no more than 1 result
        related_objects = TaggedItem.objects.get_related(self.l1, Link, num=1)
        self.assertEqual(len(related_objects), 1)
        self.assertTrue(self.l2 in related_objects)
        
    def test_get_related_objects_of_same_model_limit_related_items(self):
        related_objects = TaggedItem.objects.get_related(self.l1, Link.objects.exclude(name='link 3'))
        self.assertEqual(len(related_objects), 1)
        self.assertTrue(self.l2 in related_objects)
    
    def test_get_related_objects_of_different_model(self):
        related_objects = TaggedItem.objects.get_related(self.a1, Link)
        self.assertEqual(len(related_objects), 3)
        self.assertTrue(self.l1 in related_objects)
        self.assertTrue(self.l2 in related_objects)
        self.assertTrue(self.l3 in related_objects)
            
        Tag.objects.update_tags(self.a1, 'tag6')
        related_objects = TaggedItem.objects.get_related(self.a1, Link)
        self.assertEqual(len(related_objects), 0)
        
class TestTagUsageForQuerySet(TestCase):
    def setUp(self):
        parrot_details = (
            ('pining for the fjords', 9, True,  'foo bar'),
            ('passed on',             6, False, 'bar baz ter'),
            ('no more',               4, True,  'foo ter'),
            ('late',                  2, False, 'bar ter'),
        )
        
        for state, perch_size, perch_smelly, tags in parrot_details:
            perch = Perch.objects.create(size=perch_size, smelly=perch_smelly)
            parrot = Parrot.objects.create(state=state, perch=perch)
            Tag.objects.update_tags(parrot, tags)
    
    def test_tag_usage_for_queryset(self):
        tag_usage = Tag.objects.usage_for_queryset(Parrot.objects.filter(state='no more'), counts=True)
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 2)
        self.assertTrue(('foo', 1) in relevant_attribute_list)
        self.assertTrue(('ter', 1) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_queryset(Parrot.objects.filter(state__startswith='p'), counts=True)
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 4)
        self.assertTrue(('bar', 2) in relevant_attribute_list)
        self.assertTrue(('baz', 1) in relevant_attribute_list)
        self.assertTrue(('foo', 1) in relevant_attribute_list)
        self.assertTrue(('ter', 1) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_queryset(Parrot.objects.filter(perch__size__gt=4), counts=True)
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 4)
        self.assertTrue(('bar', 2) in relevant_attribute_list)
        self.assertTrue(('baz', 1) in relevant_attribute_list)
        self.assertTrue(('foo', 1) in relevant_attribute_list)
        self.assertTrue(('ter', 1) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_queryset(Parrot.objects.filter(perch__smelly=True), counts=True)
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 3)
        self.assertTrue(('bar', 1) in relevant_attribute_list)
        self.assertTrue(('foo', 2) in relevant_attribute_list)
        self.assertTrue(('ter', 1) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_queryset(Parrot.objects.filter(perch__smelly=True), min_count=2)
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 1)
        self.assertTrue(('foo', 2) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_queryset(Parrot.objects.filter(perch__size__gt=4))
        relevant_attribute_list = [(tag.name, hasattr(tag, 'counts')) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 4)
        self.assertTrue(('bar', False) in relevant_attribute_list)
        self.assertTrue(('baz', False) in relevant_attribute_list)
        self.assertTrue(('foo', False) in relevant_attribute_list)
        self.assertTrue(('ter', False) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_queryset(Parrot.objects.filter(perch__size__gt=99))
        relevant_attribute_list = [(tag.name, hasattr(tag, 'counts')) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 0)
        
        tag_usage = Tag.objects.usage_for_queryset(Parrot.objects.filter(Q(perch__size__gt=6) | Q(state__startswith='l')), counts=True)
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 3)
        self.assertTrue(('bar', 2) in relevant_attribute_list)
        self.assertTrue(('foo', 1) in relevant_attribute_list)
        self.assertTrue(('ter', 1) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_queryset(Parrot.objects.filter(Q(perch__size__gt=6) | Q(state__startswith='l')), min_count=2)
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 1)
        self.assertTrue(('bar', 2) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_queryset(Parrot.objects.filter(Q(perch__size__gt=6) | Q(state__startswith='l')))
        relevant_attribute_list = [(tag.name, hasattr(tag, 'counts')) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 3)
        self.assertTrue(('bar', False) in relevant_attribute_list)
        self.assertTrue(('foo', False) in relevant_attribute_list)
        self.assertTrue(('ter', False) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_queryset(Parrot.objects.exclude(state='passed on'), counts=True)
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 3)
        self.assertTrue(('bar', 2) in relevant_attribute_list)
        self.assertTrue(('foo', 2) in relevant_attribute_list)
        self.assertTrue(('ter', 2) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_queryset(Parrot.objects.exclude(state__startswith='p'), min_count=2)
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 1)
        self.assertTrue(('ter', 2) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_queryset(Parrot.objects.exclude(Q(perch__size__gt=6) | Q(perch__smelly=False)), counts=True)
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 2)
        self.assertTrue(('foo', 1) in relevant_attribute_list)
        self.assertTrue(('ter', 1) in relevant_attribute_list)
        
        tag_usage = Tag.objects.usage_for_queryset(Parrot.objects.exclude(perch__smelly=True).filter(state__startswith='l'), counts=True)
        relevant_attribute_list = [(tag.name, tag.count) for tag in tag_usage]
        self.assertEqual(len(relevant_attribute_list), 2)
        self.assertTrue(('bar', 1) in relevant_attribute_list)
        self.assertTrue(('ter', 1) in relevant_attribute_list)
        
################
# Model Fields #
################

class TestTagFieldInForms(TestCase):
    def test_tag_field_in_modelform(self):
        # Ensure that automatically created forms use TagField
        class TestForm(forms.ModelForm):
            class Meta:
                model = FormTest
                
        form = TestForm()
        self.assertEqual(form.fields['tags'].__class__.__name__, 'TagField')
    
    def test_recreation_of_tag_list_string_representations(self):
        plain = Tag.objects.create(name='plain')
        spaces = Tag.objects.create(name='spa ces')
        comma = Tag.objects.create(name='com,ma')
        self.assertEqual(edit_string_for_tags([plain]), 'plain')
        self.assertEqual(edit_string_for_tags([plain, spaces]), 'plain, spa ces')
        self.assertEqual(edit_string_for_tags([plain, spaces, comma]), 'plain, spa ces, "com,ma"')
        self.assertEqual(edit_string_for_tags([plain, comma]), 'plain "com,ma"')
        self.assertEqual(edit_string_for_tags([comma, spaces]), '"com,ma", spa ces')
    
    def test_tag_d_validation(self):
        t = TagField()
        self.assertEqual(t.clean('foo'), 'foo')
        self.assertEqual(t.clean('foo bar baz'), 'foo bar baz')
        self.assertEqual(t.clean('foo,bar,baz'), 'foo,bar,baz')
        self.assertEqual(t.clean('foo, bar, baz'), 'foo, bar, baz')
        self.assertEqual(t.clean('foo qwertyuiopasdfghjklzxcvbnmqwertyuiopasdfghjklzxcvb bar'),
            'foo qwertyuiopasdfghjklzxcvbnmqwertyuiopasdfghjklzxcvb bar')
        try:
            t.clean('foo qwertyuiopasdfghjklzxcvbnmqwertyuiopasdfghjklzxcvbn bar')
        except forms.ValidationError as exc:
            self.assertEqual(str(exc), str([six.text_type('Each tag may be no more than 50 characters long.')]))
        except Exception as exc:
            raise exc
        else:
            raise self.failureException('a ValidationError exception was supposed to have been raised.')
