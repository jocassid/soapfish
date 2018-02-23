
from __future__ import absolute_import, unicode_literals

import inspect

from lxml import etree
#from pythonic_testcase import PythonicTestCase, assert_false, assert_true
import six

from soapfish import xsd
from soapfish.namespaces import xsd as XSD_NAMESPACE
from soapfish.py2xsd import generate_xsd, generate_xsdspec, get_xsd_type




class Choice1(xsd.ComplexType):
    INHERITANCE = None
    INDICATOR = xsd.Sequence
    placeholder1 = xsd.Element(xsd.String)


class Choice2(xsd.ComplexType):
    INHERITANCE = None
    INDICATOR = xsd.Sequence
    placeholder2 = xsd.Element(xsd.String)


class ContainerWithChoices(xsd.ComplexType):
    Choice1 = xsd.Ref(__name__ + '.Choice1')
    Choice2 = xsd.Ref(__name__ + '.Choice2')


element_with_choice_schema = xsd.Schema(
    imports=[],
    includes=[],
    targetNamespace=XSD_NAMESPACE,
    elementFormDefault='unqualified',
    simpleTypes=[],
    attributeGroups=[],
    groups=[],
    complexTypes=[
        Choice1,
        Choice2,
        ContainerWithChoices,
    ],
    elements={
        'ContainerWithChoices': xsd.Element(ContainerWithChoices),
        'Choice1': xsd.Element(Choice1),
        'Choice2': xsd.Element(Choice2),
    },
)


class Test_py2xsd:
    def test_can_generate_schema_xml_containing_types_with_pattern_restriction(self):
        ns = 'http://soap.example/pattern.xsd'

        class Container(xsd.ComplexType):
            code = xsd.Element(xsd.String(pattern='[0-9]{0,5}'))
        schema = xsd.Schema(ns,
                            location=ns,
                            elementFormDefault=xsd.ElementFormDefault.QUALIFIED,
                            complexTypes=(
                                Container,
                            ),
                            elements={
                                'foo': xsd.Element(Container),
                            },
                            )
        # previously this would fail
        xsd_element = generate_xsd(schema)
        xmlschema = etree.XMLSchema(xsd_element)
        valid_xml = '<foo xmlns="%s"><code>1234</code></foo>' % ns

        def is_valid(s):
            return xmlschema.validate(etree.fromstring(s))
        assert is_valid(valid_xml)

        bad_xml = '<foo xmlns="%s"><code>abc</code></foo>' % ns
        assert not is_valid(bad_xml)

    # def test_generate_elements__elementWithChoiceContent(self):
    #
    #     xsd_element = element_with_choice_schema.elements.get('ContainerWithChoices')
    #     print('xsd_element', xsd_element)
    #
    #     print('xsd_element.substitutionGroup', xsd_element.substitutionGroup)
    #     print('xsd_element._passed_type', xsd_element._passed_type)
    #     print('isinstance(xsd_element._passed_type, six.string_types)',
    #           isinstance(xsd_element._passed_type, six.string_types))
    #     print('inspect.isclass(xsd_element._passed_type)',
    #           inspect.isclass(xsd_element._passed_type))
    #     print('xsd_element._type', xsd_element._type)
    #     print('get_xsd_type(xsd_element._type)',
    #           get_xsd_type(xsd_element._type))
    #
    #
    #     xsd_xml = generate_xsd(element_with_choice_schema)
    #     print(etree.tostring(xsd_xml, pretty_print=True))
    #     assert False

    def test_stuff(self):
        xsdspec_schema = generate_xsdspec(element_with_choice_schema)

        etree_schema_element = etree.Element(
            '{%s}schema' % XSD_NAMESPACE,
            nsmap={
                'sns': element_with_choice_schema.targetNamespace,
                'xsd': XSD_NAMESPACE,
            },
        )

        xsdspec_schema.render(
            etree_schema_element,
            xsdspec_schema,
            namespace=XSD_NAMESPACE,
            elementFormDefault=xsd.ElementFormDefault.QUALIFIED,
        )

        print('xsdspec_schema.SCHEMA', xsdspec_schema.SCHEMA)
        print('xsdspec_schema._meta.all', xsdspec_schema._meta.all)

        print(etree.tostring(etree_schema_element))
        assert False
