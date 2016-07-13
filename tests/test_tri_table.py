#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import json

from django.http import HttpResponse
from django.test import RequestFactory
from django.utils.encoding import python_2_unicode_compatible
import pytest
from tri.declarative import getattr_path
from tri.form import Field
from tri.query import Variable

from tests.helpers import verify_table_html
from tests.models import Foo, Bar

from tri.table import Struct, Table, Column, Link, render_table, render_table_to_response, register_cell_formatter


def get_data():
    return [
        Struct(foo="Hello", bar=17),
        Struct(foo="<evil/> &", bar=42)
    ]


def explicit_table():

    columns = [
        Column(name="foo"),
        Column.number(name="bar"),
    ]

    return Table(data=get_data(), columns=columns, attrs=lambda table: {'class': 'listview', 'id': 'table_id'})


def declarative_table():

    class TestTable(Table):

        class Meta:
            attrs = {
                'class': lambda table: 'listview',
                'id': lambda table: 'table_id',
            }

        foo = Column()
        bar = Column.number()

    return TestTable(data=get_data())


@pytest.mark.parametrize('table', [
    explicit_table(),
    declarative_table()
])
def test_render_impl(table):

    verify_table_html(table=table, expected_html="""
        <table class="listview" id="table_id">
            <thead>
                <tr>
                    <th class="first_column subheader">
                        <a href="?order=foo"> Foo </a>
                    </th>
                    <th class="first_column subheader">
                        <a href="?order=bar"> Bar </a>
                    </th>
                </tr>
            </thead>
            <tbody>
                <tr class="row1">
                    <td> Hello </td>
                    <td class="rj"> 17 </td>
                </tr>
                <tr class="row2">
                    <td> &lt;evil/&gt; &amp; </td>
                    <td class="rj"> 42 </td>
                </tr>
            </tbody>
        </table>""")


def test_test_declaration_merge():

    class MyTable(Table):
        class Meta:
            columns = [Column(name='foo')]

        bar = Column()

    assert {'foo', 'bar'} == {column.name for column in MyTable([]).columns}


def test_ordering():

    class MyTable(Table):
        foo = Column(after='bar')
        bar = Column()

    assert ['bar', 'foo'] == [column.name for column in MyTable([]).columns]


@pytest.mark.django_db
def test_django_table():

    f1 = Foo.objects.create(a=17, b="Hej")
    f2 = Foo.objects.create(a=42, b="Hopp")

    Bar(foo=f1, c=True).save()
    Bar(foo=f2, c=False).save()

    class TestTable(Table):
        foo__a = Column.number()
        foo__b = Column()
        foo = Column.choice_queryset(model=Foo, choices=lambda table, column: Foo.objects.all(), query__show=True, bulk__show=True, query__gui__show=True)

    t = TestTable(data=Bar.objects.all())

    t.prepare(RequestFactory().get("/", ''))

    assert list(t.bound_columns[-1].choices) == list(Foo.objects.all())
    assert list(t.bulk_form.fields[-1].choices) == list(Foo.objects.all())
    assert list(t.query_form.fields[-1].choices) == list(Foo.objects.all())

    verify_table_html(table=t, expected_html="""
        <table class="listview">
            <thead>
                <tr>
                    <th class="first_column subheader">
                        <a href="?order=foo__a"> A </a>
                    </th>
                    <th class="first_column subheader">
                        <a href="?order=foo__b"> B </a>
                    </th>
                    <th class="first_column subheader">
                        <a href="?order=foo"> Foo </a>
                    </th>
                </tr>
            </thead>
            <tbody>
                <tr class="row1" data-pk="1">
                    <td class="rj"> 17 </td>
                    <td> Hej </td>
                    <td> Foo(17, Hej) </td>

                </tr>
                <tr class="row2" data-pk="2">
                    <td class="rj"> 42 </td>
                    <td> Hopp </td>
                    <td> Foo(42, Hopp) </td>
                </tr>
            </tbody>
        </table>""")


def test_inheritance():

    class FooTable(Table):
        foo = Column()

    class BarTable(Table):
        bar = Column()

    class TestTable(FooTable, BarTable):
        another = Column()

    t = TestTable(data=[])
    assert [c.name for c in t.columns] == ['foo', 'bar', 'another']


def test_output():

    is_report = False

    class TestTable(Table):

        class Meta:
            attrs = {
                'class': 'listview',
                'id': 'table_id',
            }

        foo = Column()
        bar = Column.number()
        icon = Column.icon('history', is_report, group="group")
        edit = Column.edit(is_report, group="group")
        delete = Column.delete(is_report)

    data = [
        Struct(foo="Hello räksmörgås ><&>",
               bar=17,
               get_absolute_url=lambda: '/somewhere/'),
    ]

    verify_table_html(table=TestTable(data=data), expected_html="""
        <table class="listview" id="table_id">
            <thead>
                <tr>
                    <th class="first_column superheader" colspan="1"> </th>
                    <th class="superheader" colspan="1"> </th>
                    <th class="superheader" colspan="2"> group </th>
                    <th class="superheader" colspan="1"> </th>
                </tr>
                <tr>
                    <th class="first_column subheader">
                        <a href="?order=foo"> Foo </a>
                    </th>
                    <th class="first_column subheader">
                        <a href="?order=bar"> Bar </a>
                    </th>
                    <th class="first_column subheader thin"> </th>
                    <th class="subheader thin" title="Edit"> </th>
                    <th class="first_column subheader thin" title="Delete"> </th>
                </tr>
            </thead>
            <tbody>
                <tr class="row1">
                    <td> Hello räksmörgås &gt;&lt;&amp;&gt; </td>
                    <td class="rj"> 17 </td>
                    <td class="cj"> <i class="fa fa-lg fa-history"> </i> </td>
                    <td class="cj"> <a href="/somewhere/edit/"> <i class="fa fa-lg fa-pencil-square-o" title="Edit"> </i> </a> </td>
                    <td class="cj"> <a href="/somewhere/delete/"> <i class="fa fa-lg fa-trash-o" title="Delete"> </i> </a> </td>
                </tr>
            </tbody>
        </table>
        """)


def test_name_traversal():
    class TestTable(Table):
        foo__bar = Column(sortable=False)

    data = [Struct(foo=Struct(bar="bar"))]

    verify_table_html(table=TestTable(data=data), expected_html="""
        <table class="listview">
            <thead>
                <tr>
                    <th class="first_column subheader"> Bar </th>
                </tr>
            </thead>
            <tbody>
                <tr class="row1">
                    <td> bar </td>
                </tr>
            </tbody>
        </table>""")


# def test_tuple_data():
#     class TestTable(Table):
#
#         class Meta:
#             sortable = False
#
#         a = Column()
#         b = Column()
#         c = Column()
#
#     data = [('a', 'b', 'c')]
#
#     verify_table_html(TestTable(data=data), """
#         <table class="listview">
#             <thead>
#                 <tr>
#                     <th class="first_column subheader"> A </th>
#                     <th class="first_column subheader"> B </th>
#                     <th class="first_column subheader"> C </th>
#                 </tr>
#             </thead>
#             <tbody>
#                 <tr class="row1">
#                     <td> a </td>
#                     <td> b </td>
#                     <td> c </td>
#                 </tr>
#             </tbody>
#         </table>""")


# def test_dict_data():
#     class TestTable(Table):
#         class Meta:
#             sortable = False
#         a = Column()
#         b = Column()
#         c = Column()
#
#     data = [{'a': 'a', 'b': 'b', 'c': 'c'}]
#
#     verify_table_html(TestTable(data=data), """
#         <table class="listview">
#              <thead>
#                  <tr>
#                      <th class="first_column subheader"> A </th>
#                      <th class="first_column subheader"> B </th>
#                      <th class="first_column subheader"> C </th>
#                  </tr>
#              </thead>
#              <tbody>
#                  <tr class="row1">
#                      <td> a </td>
#                      <td> b </td>
#                      <td> c </td>
#                  </tr>
#              </tbody>
#          </table>""")


class NoSortTable(Table):
    class Meta:
        sortable = False


def test_display_name():
    class TestTable(NoSortTable):
        foo = Column(display_name="Bar")

    data = [Struct(foo="foo")]

    verify_table_html(table=TestTable(data=data), expected_html="""
        <table class="listview">
            <thead>
                <tr>
                    <th class="first_column subheader"> Bar </th>
                </tr>
            </thead>
            <tbody>
                <tr class="row1">
                    <td> foo </td>
                </tr>
            </tbody>
        </table>""")


def test_link():
    class TestTable(NoSortTable):
        foo = Column.link(cell__url='https://whereever', cell__url_title="whatever")
        bar = Column.link(cell__value='bar', cell__url_title=lambda **_: "url_title_goes_here")

    data = [Struct(foo='foo', bar=Struct(get_absolute_url=lambda: '/get/absolute/url/result'))]

    verify_table_html(table=TestTable(data=data), expected_html="""
        <table class="listview">
            <thead>
                <tr>
                    <th class="first_column subheader"> Foo </th>
                    <th class="first_column subheader"> Bar </th>
                </tr>
            </thead>
            <tbody>
                <tr class="row1">
                    <td> <a href="https://whereever" title="whatever"> foo </a> </td>
                    <td> <a href="/get/absolute/url/result" title="url_title_goes_here"> bar </a> </td>
                </tr>
            </tbody>
        </table>""")


def test_css_class():
    class TestTable(NoSortTable):
        foo = Column(attrs__class__some_class=True)
        legacy_foo = Column(css_class={"some_other_class"})
        legacy_bar = Column(cell__attrs={'class': 'foo'},
                            cell__attrs__class__bar=True)

    data = [Struct(foo="foo", legacy_foo="foo", legacy_bar="bar")]

    verify_table_html(table=TestTable(data=data), expected_html="""
    <table class="listview">
        <thead>
            <tr>
                <th class="first_column some_class subheader"> Foo </th>
                <th class="first_column some_other_class subheader"> Legacy foo </th>
                <th class="first_column subheader"> Legacy bar </th>
            </tr>
        </thead>
        <tbody>
            <tr class="row1">
                <td> foo </td>
                <td> foo </td>
                <td class="bar foo"> bar </td>
            </tr>
        </tbody>
    </table>""")


def test_header_url():
    class TestTable(NoSortTable):
        foo = Column(url="/some/url")

    data = [Struct(foo="foo")]

    verify_table_html(table=TestTable(data=data), expected_html="""
    <table class="listview">
        <thead>
            <tr><th class="first_column subheader">
                <a href="/some/url"> Foo </a>
            </th></tr>
        </thead>
        <tbody>
            <tr class="row1">
                <td> foo </td>
            </tr>
        </tbody>
    </table>""")


def test_title():
    class TestTable(NoSortTable):
        foo = Column(title="Some title")

    data = [Struct(foo="foo")]

    verify_table_html(table=TestTable(data), expected_html="""
    <table class="listview">
        <thead>
            <tr><th class="first_column subheader" title="Some title"> Foo </th></tr>
        </thead>\
        <tbody>
            <tr class="row1">
                <td> foo </td>
            </tr>
        </tbody>
    </table>""")


def test_show():
    class TestTable(NoSortTable):
        foo = Column()
        bar = Column(show=False)

    data = [Struct(foo="foo", bar="bar")]

    verify_table_html(table=TestTable(data=data), expected_html="""
    <table class="listview">
        <thead>
            <tr><th class="first_column subheader"> Foo </th></tr>
        </thead>
        <tbody>
            <tr class="row1">
                <td> foo </td>
            </tr>
        </tbody>
    </table>""")


def test_show_lambda():
    def show_callable(table, column):
        assert isinstance(table, TestTable)
        assert column.name == 'bar'
        return False

    class TestTable(NoSortTable):
        foo = Column()
        bar = Column.icon('foo', show=show_callable)

    data = [Struct(foo="foo", bar="bar")]

    verify_table_html(table=TestTable(data=data), expected_html="""
    <table class="listview">
        <thead>
            <tr><th class="first_column subheader"> Foo </th></tr>
        </thead>
        <tbody>
            <tr class="row1">
                <td> foo </td>
            </tr>
        </tbody>
    </table>""")


def test_attr():
    class TestTable(NoSortTable):
        foo = Column()
        bar = Column(attr='foo')

    data = [Struct(foo="foo")]

    verify_table_html(table=TestTable(data=data), expected_html="""
    <table class="listview">
        <thead>
            <tr>
                <th class="first_column subheader"> Foo </th>
                <th class="first_column subheader"> Bar </th>
            </tr>
        </thead>
        <tbody>
            <tr class="row1">
                <td> foo </td>
                <td> foo </td>
            </tr>
        </tbody>
    </table>""")


def test_attrs():
    class TestTable(NoSortTable):
        class Meta:
            attrs = {
                'class': 'classy',
                'foo': lambda table: 'bar'
            }
            row__attrs = {
                'class': 'classier',
                'foo': lambda table, row: "barier"
            }

        yada = Column()

    verify_table_html(table=TestTable(data=[Struct(yada=1), Struct(yada=2)]), expected_html="""
        <table class="classy listview" foo="bar">
            <thead>
                <tr>
                  <th class="first_column subheader"> Yada </th>
                </tr>
            </thead>
            <tbody>
                <tr class="classier row1" foo="barier">
                    <td> 1 </td>
                </tr>
                <tr class="classier row2" foo="barier">
                    <td> 2 </td>
                </tr>
            </tbody>
        </table>""")


def test_attrs_new_syntax():
    class TestTable(NoSortTable):
        class Meta:
            attrs__class__classy = True
            attrs__foo = lambda table: 'bar'

            row__attrs__class__classier = True
            row__attrs__foo = lambda table: "barier"

        yada = Column()

    verify_table_html(table=TestTable(data=[Struct(yada=1), Struct(yada=2)]), expected_html="""
        <table class="classy listview" foo="bar">
            <thead>
                <tr>
                  <th class="first_column subheader"> Yada </th>
                </tr>
            </thead>
            <tbody>
                <tr class="classier row1" foo="barier">
                    <td> 1 </td>
                </tr>
                <tr class="classier row2" foo="barier">
                    <td> 2 </td>
                </tr>
            </tbody>
        </table>""")


def test_column_presets():
    is_report = False

    class TestTable(NoSortTable):
        icon = Column.icon(is_report)
        edit = Column.edit(is_report)
        delete = Column.delete(is_report)
        download = Column.download(is_report)
        run = Column.run(is_report)
        select = Column.select(is_report)
        boolean = Column.boolean(is_report)
        link = Column.link(cell__format="Yadahada name")
        number = Column.number()

    data = [Struct(pk=123,
                   get_absolute_url=lambda: "http://yada/",
                   boolean=lambda: True,
                   link=Struct(get_absolute_url=lambda: "http://yadahada/"),
                   number=123)]
    verify_table_html(table=TestTable(data=data), expected_html="""
        <table class="listview">
            <thead>
                <tr>
                    <th class="first_column subheader thin" />
                    <th class="first_column subheader thin" title="Edit" />
                    <th class="first_column subheader thin" title="Delete" />
                    <th class="first_column subheader thin" title="Download" />
                    <th class="first_column subheader thin" title="Run"> Run </th>
                    <th class="first_column nopad subheader thin" title="Select all">
                        <i class="fa fa-check-square-o" />
                    </th>
                    <th class="first_column subheader"> Boolean </th>
                    <th class="first_column subheader"> Link </th>
                    <th class="first_column subheader"> Number </th>
                </tr>
            </thead>
            <tbody>
                <tr class="row1" data-pk="123">
                    <td class="cj"> <i class="fa fa-lg fa-False" /> </td>
                    <td class="cj"> <a href="http://yada/edit/"> <i class="fa fa-lg fa-pencil-square-o" title="Edit" /> </a> </td>
                    <td class="cj"> <a href="http://yada/delete/"> <i class="fa fa-lg fa-trash-o" title="Delete" /> </a> </td>
                    <td class="cj"> <a href="http://yada/download/"> <i class="fa fa-lg fa-download" title="Download" /> </a> </td>
                    <td> <a href="http://yada/run/"> Run </a> </td>
                    <td class="cj"> <input class="checkbox" name="pk_123" type="checkbox"/> </td> <td class="cj"> <i class="fa fa-check" title="Yes" /> </td>
                    <td> <a href="http://yadahada/"> Yadahada name </a> </td>
                    <td class="rj"> 123 </td>
                </tr>
            </tbody>
        </table>""")


@pytest.mark.django_db
def test_django_table_pagination():

    for x in range(30):
        Foo(a=x, b="foo").save()

    class TestTable(Table):
        a = Column.number(sortable=False)  # turn off sorting to not get the link with random query params
        b = Column(show=False)  # should still be able to filter on this though!

    verify_table_html(table=TestTable(data=Foo.objects.all()),
                      query=dict(page_size=2, page=2, query='b="foo"'),
                      expected_html="""
        <table class="listview">
            <thead>
                <tr>
                    <th class="first_column subheader"> A </th>
                </tr>
            </thead>
            <tbody>
                <tr class="row1" data-pk="3">
                    <td class="rj"> 2 </td>
                </tr>
                <tr class="row2" data-pk="4">
                    <td class="rj"> 3 </td>
                </tr>
            </tbody>
        </table>""")


def test_links():
    class TestTable(NoSortTable):
        foo = Column(title="Some title")

    data = [Struct(foo="foo")]

    links = [
        Link('Foo', url='/foo/', show=lambda table: table.data is not data),
        Link('Bar', url='/bar/', show=lambda table: table.data is data),
        Link('Baz', url='/bar/', group='Other'),
        Link('Qux', url='/bar/', group='Other'),
        Link.icon('icon_foo', title='Icon foo', url='/icon_foo/'),
    ]

    verify_table_html(table=TestTable(data=data),
                      find=dict(class_='links'),
                      links=links,
                      expected_html="""
        <div class="links">
            <div class="dropdown">
                <a class="button button-primary" data-target="#" data-toggle="dropdown" href="/page.html" id="id_dropdown_other" role="button">
                    Other <i class="fa fa-lg fa-caret-down" />
                </a>
                <ul aria-labelledby="id_dropdown_Other" class="dropdown-menu" role="menu">
                    <li role="presentation">
                        <a href="/bar/" role="menuitem"> Baz </a>
                    </li>
                    <li role="presentation">
                        <a href="/bar/" role="menuitem"> Qux </a>
                    </li>
                </ul>
            </div>

            <a href="/bar/"> Bar </a>

            <a href="/icon_foo/"> <i class="fa fa-icon_foo" /> Icon foo </a>
        </div>""")


@pytest.mark.django_db
def test_bulk_edit():
    assert Foo.objects.all().count() == 0

    Foo(a=1, b="").save()
    Foo(a=2, b="").save()
    Foo(a=3, b="").save()
    Foo(a=4, b="").save()

    class TestTable(Table):
        a = Column.number(sortable=False, bulk__show=True)  # turn off sorting to not get the link with random query params
        b = Column(bulk__show=True)

    result = render_table(request=RequestFactory(HTTP_REFERER='/').get("/", dict(pk_1='', pk_2='', a='0', b='changed')), table=TestTable(data=Foo.objects.all()))
    assert '<form method="post" action=".">' in result
    assert '<input type="submit" class="button" value="Bulk change"/>' in result

    render_table(request=RequestFactory(HTTP_REFERER='/').post("/", dict(pk_1='', pk_2='', a='0', b='changed')), table=TestTable(data=Foo.objects.all()))

    assert [(x.pk, x.a, x.b) for x in Foo.objects.all()] == [
        (1, 0, u'changed'),
        (2, 0, u'changed'),
        (3, 3, u''),
        (4, 4, u''),
    ]


@pytest.mark.django_db
def test_query():
    assert Foo.objects.all().count() == 0

    Foo(a=1, b="foo").save()
    Foo(a=2, b="foo").save()
    Foo(a=3, b="bar").save()
    Foo(a=4, b="bar").save()

    class TestTable(Table):
        a = Column.number(sortable=False, query__show=True, query__gui__show=True)  # turn off sorting to not get the link with random query params
        b = Column.substring(query__show=True, query__gui__show=True)

        class Meta:
            sortable = False

    verify_table_html(query=dict(query='asdasdsasd'), table=TestTable(data=Foo.objects.all()), find=dict(id='tri_query_error'), expected_html='<div id="tri_query_error">Invalid syntax for query</div>')

    verify_table_html(query=dict(a='1'), table=TestTable(data=Foo.objects.all()), find=dict(name='tbody'), expected_html="""
    <tbody>
        <tr class="row1" data-pk="1">
            <td class="rj">
                1
            </td>
            <td>
                foo
            </td>
        </tr>
    </table>""")
    verify_table_html(query=dict(b='bar'), table=TestTable(data=Foo.objects.all()), find=dict(name='tbody'), expected_html="""
    <tbody>
        <tr class="row1" data-pk="3">
            <td class="rj">
                3
            </td>
            <td>
                bar
            </td>
        </tr>
        <tr class="row2" data-pk="4">
            <td class="rj">
                4
            </td>
            <td>
                bar
            </td>
        </tr>
    </tbody>""")
    verify_table_html(query=dict(query='b="bar"'), table=TestTable(data=Foo.objects.all()), find=dict(name='tbody'), expected_html="""
    <tbody>
        <tr class="row1" data-pk="3">
            <td class="rj">
                3
            </td>
            <td>
                bar
            </td>
        </tr>
        <tr class="row2" data-pk="4">
            <td class="rj">
                4
            </td>
            <td>
                bar
            </td>
        </tr>
    </tbody>""")
    verify_table_html(query=dict(b='fo'), table=TestTable(data=Foo.objects.all()), find=dict(name='tbody'), expected_html="""
    <tbody>
        <tr class="row1" data-pk="1">
            <td class="rj">
                1
            </td>
            <td>
                foo
            </td>
        </tr>
        <tr class="row2" data-pk="2">
            <td class="rj">
                2
            </td>
            <td>
                foo
            </td>
        </tr>
    </table>""")


def test_cell_template():
    def explode(**_):
        assert False

    class TestTable(NoSortTable):
        foo = Column(cell__template='test_cell_template.html', cell__format=explode, cell__url=explode, cell__url_title=explode)

    data = [Struct(foo="sentinel")]

    verify_table_html(table=TestTable(data=data), expected_html="""
        <table class="listview">
            <thead>
                <tr><th class="first_column subheader"> Foo </th></tr>
            </thead>
            <tbody>
                <tr class="row1">
                    Custom rendered: sentinel
                </tr>
            </tbody>
        </table>""")


def test_no_header_template():
    class TestTable(NoSortTable):
        class Meta:
            header__template = None

        foo = Column()

    data = [Struct(foo="bar")]

    verify_table_html(table=TestTable(data=data), expected_html="""
        <table class="listview">
            <tbody>
                <tr class="row1">
                    <td>
                        bar
                    </td>
                </tr>
            </tbody>
        </table>""")


def test_row_template():
    class TestTable(NoSortTable):
        foo = Column()
        bar = Column()

        class Meta:
            row__template = lambda table: 'test_table_row.html'

    data = [Struct(foo="sentinel", bar="schmentinel")]

    verify_table_html(table=TestTable(data=data), expected_html="""
        <table class="listview">
            <thead>
                <tr>
                  <th class="first_column subheader"> Foo </th>
                  <th class="first_column subheader"> Bar </th>
                </tr>
            </thead>
            <tbody>

             All columns:
             <td> sentinel </td>
             <td> schmentinel </td>

             One by name:
              <td> sentinel </td>
            </tbody>
        </table>""")


def test_cell_lambda():
    class TestTable(NoSortTable):
        sentinel1 = 'sentinel1'

        sentinel2 = Column(cell__value=lambda table, column, row: '%s %s %s' % (table.sentinel1, column.name, row.sentinel3))

    data = [Struct(sentinel3="sentinel3")]

    verify_table_html(table=TestTable(data=data), expected_html="""
        <table class="listview">
            <thead>
                <tr><th class="first_column subheader"> Sentinel2 </th></tr>
            </thead>
            <tbody>
                <tr class="row1">
                    <td>
                        sentinel1 sentinel2 sentinel3
                    </td>
                </tr>
            </tbody>
        </table>""")


def test_auto_rowspan_and_render_twice():
    class TestTable(NoSortTable):
        foo = Column(auto_rowspan=True)

    data = [
        Struct(foo=1),
        Struct(foo=1),
        Struct(foo=2),
        Struct(foo=2),
    ]

    expected = """
        <table class="listview">
            <thead>
                <tr><th class="first_column subheader"> Foo </th></tr>
            </thead>
            <tbody>
                <tr class="row1">
                    <td rowspan="2"> 1 </td>
                </tr>
                <tr class="row2">
                    <td style="display: none"> 1 </td>
                </tr>
                <tr class="row1">
                    <td rowspan="2"> 2 </td>
                </tr>
                <tr class="row2">
                    <td style="display: none"> 2 </td>
                </tr>
            </tbody>
        </table>"""

    t = TestTable(data=data)
    verify_table_html(table=t, expected_html=expected)
    verify_table_html(table=t, expected_html=expected)


def test_render_table_to_response():
    class TestTable(NoSortTable):
        foo = Column(display_name="Bar")

    data = [Struct(foo="foo")]

    response = render_table_to_response(RequestFactory().get('/'), TestTable(data=data))
    assert isinstance(response, HttpResponse)
    assert b'<table' in response.content


@pytest.mark.django_db
def test_default_formatters():
    class TestTable(NoSortTable):
        foo = Column()

    @python_2_unicode_compatible
    class SomeType(object):
        def __str__(self):
            return 'this should not end up in the table'

    register_cell_formatter(SomeType, lambda table, column, row, value: 'sentinel')

    assert Foo.objects.all().count() == 0

    Foo(a=1, b="3").save()
    Foo(a=2, b="5").save()

    data = [
        Struct(foo=1),
        Struct(foo=True),
        Struct(foo=False),
        Struct(foo=[1, 2, 3]),
        Struct(foo=SomeType()),
        Struct(foo=Foo.objects.all()),
        Struct(foo=None),
    ]

    verify_table_html(table=TestTable(data=data), expected_html="""
        <table class="listview">
            <thead>
                <tr><th class="first_column subheader"> Foo </th></tr>
            </thead>
            <tbody>
                <tr class="row1">
                    <td>
                        1
                    </td>
                </tr>
                <tr class="row2">
                    <td>
                        Yes
                    </td>
                </tr>
                <tr class="row1">
                    <td>
                        No
                    </td>
                </tr>
                <tr class="row2">
                    <td>
                        1, 2, 3
                    </td>
                </tr>
                <tr class="row1">
                    <td>
                        sentinel
                    </td>
                </tr>
                <tr class="row2">
                    <td>
                        Foo(1, 3), Foo(2, 5)
                    </td>
                </tr>
                <tr class="row1">
                    <td>
                    </td>
                </tr>
            </tbody>
        </table>""")


@pytest.mark.django_db
def test_choice_queryset():
    assert Foo.objects.all().count() == 0

    Foo.objects.create(a=1)
    Foo.objects.create(a=2)

    class FooTable(Table):
        foo = Column.choice_queryset(query__show=True, query__gui__show=True, bulk__show=True, choices=lambda table, column: Foo.objects.filter(a=1))

        class Meta:
            model = Foo

    foo_table = FooTable(data=Foo.objects.all())
    foo_table.prepare(RequestFactory().get("/"))

    assert repr(foo_table.bound_columns[0].choices) == repr(Foo.objects.filter(a=1))
    assert repr(foo_table.bulk_form.fields[0].choices) == repr(list(Foo.objects.filter(a=1)))
    assert repr(foo_table.query_form.fields[0].choices) == repr(list(Foo.objects.filter(a=1)))


@pytest.mark.django_db
def test_multi_choice_queryset():
    assert Foo.objects.all().count() == 0

    Foo.objects.create(a=1)
    Foo.objects.create(a=2)
    Foo.objects.create(a=3)
    Foo.objects.create(a=4)

    class FooTable(Table):
        foo = Column.multi_choice_queryset(query__show=True, query__gui__show=True, bulk__show=True, choices=lambda table, column: Foo.objects.exclude(a=3).exclude(a=4))

        class Meta:
            model = Foo

    foo_table = FooTable(data=Foo.objects.all())
    foo_table.prepare(RequestFactory().get("/"))

    assert repr(foo_table.bound_columns[0].choices) == repr(Foo.objects.exclude(a=3).exclude(a=4))
    assert repr(foo_table.bulk_form.fields[0].choices) == repr(list(Foo.objects.exclude(a=3).exclude(a=4)))
    assert repr(foo_table.query_form.fields[0].choices) == repr(list(Foo.objects.exclude(a=3).exclude(a=4)))


@pytest.mark.django_db
def test_query_namespace_inject():
    class FooException(Exception):
        pass

    def post_validation(form):
        del form
        raise FooException()

    with pytest.raises(FooException):
        foo = Table(
            data=[],
            model=Foo,
            request=Struct(method='POST', POST={'-': '-'}, GET=Struct(urlencode=lambda: None)),
            columns=[Column(name='foo', query__show=True, query__gui__show=True)],
            query__gui__post_validation=post_validation)
        foo.prepare(foo.request)


def test_float():
    x = Column.float()
    assert getattr_path(x, 'query__class') == Variable.float
    assert getattr_path(x, 'bulk__class') == Field.float


def test_integer():
    x = Column.integer()
    assert getattr_path(x, 'query__class') == Variable.integer
    assert getattr_path(x, 'bulk__class') == Field.integer


def test_date():
    x = Column.date()
    # TODO: should check for Variable.date
    assert getattr_path(x, 'query__gui__class') == Field.date
    assert getattr_path(x, 'bulk__class') == Field.date


def test_datetime():
    x = Column.datetime()
    # TODO: should check for Variable.datetime
    assert getattr_path(x, 'query__gui__class') == Field.datetime
    assert getattr_path(x, 'bulk__class') == Field.datetime


def test_email():
    x = Column.email()
    # TODO: should check for Variable.email
    assert getattr_path(x, 'query__gui__class') == Field.email
    assert getattr_path(x, 'bulk__class') == Field.email


def test_extra():
    class TestTable(Table):
        foo = Column(extra__foo=1, extra__bar=2)

    assert TestTable(data=[]).columns[0].extra.foo == 1
    assert TestTable(data=[]).columns[0].extra.bar == 2


def test_from_model():
    t = Table.from_model(
        model=Foo,
        data=Foo.objects.all(),
        column__a__display_name='Some a',
        column__a__extra__stuff='Some stuff',
    )
    assert [x.name for x in t.columns] == ['id', 'a', 'b']
    assert [x.name for x in t.columns if x.show] == ['a', 'b']
    t.prepare(RequestFactory().get("/"))
    assert 'Some a' == t.bound_column_by_name['a'].display_name
    assert 'Some stuff' == t.bound_column_by_name['a'].extra.stuff


@pytest.mark.django_db
def test_ajax_endpoint():
    f1 = Foo.objects.create(a=17, b="Hej")
    f2 = Foo.objects.create(a=42, b="Hopp")

    Bar(foo=f1, c=True).save()
    Bar(foo=f2, c=False).save()

    class TestTable(Table):
        foo = Column.choice_queryset(
            model=Foo,
            choices=lambda table, column: Foo.objects.all(),
            query__gui__extra__endpoint_attr='b',
            query__show=True,
            bulk__show=True,
            query__gui__show=True)

    result = render_table(request=RequestFactory().get("/", {'__query__gui__field__foo': 'hopp'}), table=TestTable(data=Bar.objects.all()))
    assert json.loads(result.content.decode('utf8')) == [{'id': 2, 'text': 'Hopp'}]


def test_ajax_data_endpoint():

    class TestTable(Table):
        class Meta:
            endpoint__data = lambda table, key, value: [{cell.bound_column.name: cell.value for cell in row} for row in table]

        foo = Column()
        bar = Column()

    table = TestTable(data=[
        Struct(foo=1, bar=2),
        Struct(foo=3, bar=4),
    ])

    result = render_table(request=RequestFactory().get("/", {'__data': ''}), table=table)
    assert json.loads(result.content.decode('utf8')) == [dict(foo=1, bar=2), dict(foo=3, bar=4)]


def test_table_iteration():

    class TestTable(Table):
        class Meta:
            data = [
                Struct(foo='a', bar=1),
                Struct(foo='b', bar=2)
            ]

        foo = Column()
        bar = Column(cell__value=lambda row, **_: row['bar'] + 1)

    table = TestTable(request=RequestFactory().get('/'))

    expected = [
        dict(foo='a', bar=2),
        dict(foo='b', bar=3),
    ]
    assert expected == [{bound_cell.bound_column.name: bound_cell.value for bound_cell in bound_row} for bound_row in table]


def test_ajax_custom_endpoint():
    class TestTable(Table):
        class Meta:
            endpoint__foo = lambda table, key, value: dict(baz=value)
        spam = Column()

    result = render_table(request=RequestFactory().get("/", {'__foo': 'bar'}), table=TestTable(data=[]))
    assert json.loads(result.content.decode('utf8')) == dict(baz='bar')
