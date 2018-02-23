#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function

import argparse
import imp
import inspect
import logging
import sys

import six
from lxml import etree

from . import namespaces as ns, xsd, xsdspec
from .utils import uncapitalize, walk_schema_tree

NUMERIC_TYPES = [
    xsd.Decimal, xsd.Integer, xsd.Int, xsd.Long, xsd.Short, xsd.UnsignedByte, xsd.UnsignedInt, xsd.UnsignedLong,
    xsd.UnsignedShort, xsd.Double, xsd.Float, xsd.Byte,
]

STRING_TYPES = [xsd.QName, xsd.AnyURI, xsd.Base64Binary, xsd.QName, xsd.AnyType, xsd.Duration]

ALL_TYPES = NUMERIC_TYPES + STRING_TYPES


logger = logging.getLogger('soapfish')


# --- Helpers -----------------------------------------------------------------
def get_xsd_type(_type):
    '''
    Check if type_ is a basic type in the XSD scope otherwise it must be user
    defined type.
    '''
    base_class = _type.__class__.__bases__[0]
    if base_class == xsd.SimpleType or _type.__class__ in ALL_TYPES:
        return 'xsd:' + uncapitalize(_type.__class__.__name__)
    else:
        return 'sns:' + uncapitalize(_type.__class__.__name__)


def xsd_attribute(attribute):
    xsdattr = xsdspec.Attribute()
    xsdattr.name = attribute._name
    xsdattr.use = attribute.use
    xsdattr.type = get_xsd_type(attribute._type)
    return xsdattr


def create_xsd_element(element):
    xsd_element = xsdspec.Element()
    xsd_element.name = element.tagname if element.tagname else element._name
    xsd_element.nillable = element.nillable
    xsd_element.minOccurs = element._minOccurs
    if hasattr(element, '_maxOccurs'):
        xsd_element.maxOccurs = element._maxOccurs

    # SimpleType defined in place.
    parent_type = element._type.__class__.__bases__[0]
    _type = element._type

    if not inspect.isclass(element._passed_type):
        xsd_element.simpleType = xsdspec.SimpleType()
        xsd_element.simpleType.restriction = xsdspec.Restriction()
        xsd_element.simpleType.restriction.base = get_xsd_type(element._type)

        if (
            hasattr(element._type, 'enumeration') and element._type.enumeration and
            parent_type == xsd.SimpleType
        ):
            for value in element._type.enumeration:
                enum = xsdspec.Enumeration.create(value)
                xsd_element.simpleType.restriction.enumerations.append(enum)

        if hasattr(_type, 'fractionDigits') and _type.fractionDigits:
            xsd_element.simpleType.restriction.fractionDigits = xsdspec.RestrictionValue(value=str(_type.fractionDigits))

        if hasattr(_type, 'pattern') and _type.pattern:
            xsd_element.simpleType.restriction.pattern = xsdspec.Pattern(value=str(_type.pattern))

        if hasattr(_type, 'minInclusive') and _type.minInclusive:
            xsd_element.simpleType.restriction.minInclusive = xsdspec.RestrictionValue(value=str(_type.minInclusive))

        if hasattr(_type, 'minExclusive') and _type.minExclusive:
            xsd_element.simpleType.restriction.minExclusive = xsdspec.RestrictionValue(value=str(_type.minExclusive))

        if hasattr(_type, 'maxExclusive') and _type.maxExclusive:
            xsd_element.simpleType.restriction.maxExclusive = xsdspec.RestrictionValue(value=str(_type.maxExclusive))

        if hasattr(_type, 'maxInclusive') and _type.maxInclusive:
            xsd_element.simpleType.restriction.maxInclusive = xsdspec.RestrictionValue(value=str(_type.maxInclusive))

        if hasattr(_type, 'totalDigits') and _type.totalDigits:
            xsd_element.simpleType.restriction.totalDigits = xsdspec.RestrictionValue(value=str(_type.totalDigits))
    else:
        xsd_element.type = get_xsd_type(element._type)
    return xsd_element


def xsd_complexType(complexType, named=True):
    xsd_ct = xsdspec.XSDComplexType()
    if named:
        xsd_ct.name = uncapitalize(complexType.__name__)

    for attribute in complexType._meta.attributes:
        xsd_attr = xsd_attribute(attribute)
        xsd_ct.attributes.append(xsd_attr)

    # Elements can be wrapped with few type of containers:
    # sequence, all, choice or it can be a complexContent with
    # extension or restriction.
    if hasattr(complexType, 'INDICATOR') and complexType.INDICATOR is not None:
        xsd_sequence = xsdspec.Sequence()
        setattr(xsd_ct, complexType.INDICATOR.__name__.lower(), xsd_sequence)
        container = xsd_sequence
    else:
        container = xsd_ct

    for element in complexType._meta.fields:
        for element_ in element.xsd_elements():
            if element_._type is None:
                # The type must be known in order to generate a valid schema. The
                # error occured when using the built-in WSDL generation but I was
                # unable to reproduce the error condition in a test case.
                # Forcing type evaluation fixed the problem though.
                element_._evaluate_type()
            xsd_element = create_xsd_element(element_)
            container.elements.append(xsd_element)
    return xsd_ct


def xsd_simpleType(st):
    xsd_simpleType = xsdspec.SimpleType()
    xsd_simpleType.name = uncapitalize(st.__name__)
    xsd_restriction = xsdspec.Restriction()
    xsd_restriction.base = get_xsd_type(st.__bases__[0]())
    if hasattr(st, 'enumeration') and st.enumeration:
        for enum in st.enumeration:
            xsd_restriction.enumerations.append(xsdspec.Enumeration.create(enum))
    if hasattr(st, 'fractionDigits') and st.fractionDigits:
        xsd_restriction.fractionDigits = xsdspec.RestrictionValue(value=st.fractionDigits)
    elif hasattr(st, 'pattern') and st.pattern:
        xsd_restriction.pattern = xsdspec.Pattern(value=st.pattern)
    xsd_simpleType.restriction = xsd_restriction
    return xsd_simpleType


def build_imports(xsdspec_schema, imports):
    """

    :param xsdspec_schema: A soapfish.xsdspec.Schema object.
    :param imports: Imports from the soapfish.xsd.Schema object
    :return:
    """
    for _import in imports:
        xsdspec_import = xsdspec.Import()
        xsdspec_import.namespace = _import.targetNamespace
        if _import.location:
            xsdspec_import.schemaLocation = _import.location
        xsdspec_schema.imports.append(xsdspec_import)


def build_includes(xsd_schema, includes):
    for _include in includes:
        xsd_include = xsdspec.Include()
        if _include.location:
            xsd_include.schemaLocation = _include.location
        xsd_schema.includes.append(xsd_include)


def generate_xsdspec(xsd_schema):
    """

    :param xsd_schema: A soapfish.xsd.Schema object
    :return: A soapfish.xsdspec.Schema object
    """
    xsdspec_schema = xsdspec.Schema()
    xsdspec_schema.targetNamespace = xsd_schema.targetNamespace
    xsdspec_schema.elementFormDefault = xsd_schema.elementFormDefault

    build_imports(xsdspec_schema, xsd_schema.imports)
    build_includes(xsdspec_schema, xsd_schema.includes)
    for st in xsd_schema.simpleTypes:
        xsd_st = xsd_simpleType(st)
        xsdspec_schema.simpleTypes.append(xsd_st)

    for ct in xsd_schema.complexTypes:
        xsdspec_ct = xsd_complexType(ct)
        xsdspec_schema.complexTypes.append(xsdspec_ct)

    generate_elements(xsdspec_schema, xsd_schema)
    return xsdspec_schema


def generate_elements(xsdspec_schema, xsd_schema):
    for name, xsd_element in six.iteritems(xsd_schema.elements):
        xsdspec_element = xsdspec.Element()
        xsdspec_element.name = name

        # TODO: Support non-string values for substitutionGroup:
        if xsd_element.substitutionGroup is not None:
            value = xsd_element.substitutionGroup
            xsdspec_element.substitutionGroup = value if value.startswith('sns:') else 'sns:%s' % value

        if isinstance(xsd_element._passed_type, six.string_types) or inspect.isclass(xsd_element._passed_type):
            xsdspec_element.type = get_xsd_type(xsd_element._type)
        else:
            xsdspec_element.complexType = xsd_complexType(xsd_element._type.__class__, named=False)

        xsdspec_schema.elements.append(xsdspec_element)


def generate_xsd(schema):
    """
    Convert a soapfish.xsd.Schema into an etree.Element representing a W3C
    xs:schema element.
    :param schema: A soapfish.xsd.Schema object
    :return: A soapfish.xsdspec instance
    """
    xsdspec_schema = generate_xsdspec(schema)

    etree_schema_element = etree.Element(
        '{%s}schema' % ns.xsd,
        nsmap={
            'sns': schema.targetNamespace,
            'xsd': xsdspec.XSD_NAMESPACE,
        },
    )

    xsdspec_schema.render(etree_schema_element,
                      xsdspec_schema,
                      namespace=xsdspec.XSD_NAMESPACE,
                      elementFormDefault=xsd.ElementFormDefault.QUALIFIED)
    return etree_schema_element


def schema_validator(schemas):
    """
    Return a callable for the specified soapfish schemas which can be used
    to validate (etree) xml documents.
    The method takes care of resolving imported (soapfish) schemas but prevents
    any unwanted network access.
    """
    class SchemaResolver(etree.Resolver):

        def __init__(self, schemas, *args, **kwargs):
            super(SchemaResolver, self).__init__(*args, **kwargs)
            self.lookup = walk_schema_tree(schemas, lambda x: x)

        def resolve(self, url, id_, context):
            if url in self.lookup:
                schema_string = etree.tostring(generate_xsd(self.lookup[url]))
                return self.resolve_string(schema_string, context)
            # prevent unwanted network access
            raise ValueError('Cannot resolve %r - not a known soapfish schema' % url)

    parser = etree.XMLParser(load_dtd=True)
    resolver = SchemaResolver(schemas)
    parser.resolvers.add(resolver)

    # unfortunately we have to parse the whole schema from string so we are
    # able to configure a custom resolver just for this instance. This seems to
    # a limitation of the lxml API.
    # I tried to use '.parser.resolvers.add()' on an ElementTree instance but
    # that uses the default parser which refers to a shared _ResolverRegistry
    # which can not be cleared without having references to all registered
    # resolvers (and we don't know these instances). Also I noticed many test
    # failures (only when running all tests!) and strange behavior in
    # "resolve()" (self.lookup was empty unless doing repr() on the
    # instance attribute first).
    # Also having shared resolvers is not a good idea because a user might want
    # to have different validator instances at the same time (possibly with
    # conflicting namespace urls).
    schema_xml = b''.join(etree.tostring(generate_xsd(s)) for s in schemas)
    schema_element = etree.fromstring(schema_xml, parser)
    xml_schema = etree.XMLSchema(schema_element)
    return xml_schema.assertValid


# --- Program -----------------------------------------------------------------


def main(argv=None):
    stdout = getattr(sys.stdout, 'buffer', sys.stdout)

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Generates an XSD document from a Python module.',
    )
    parser.add_argument('module', help='The path to a python module.')
    parser.add_argument('output', help='Output path for XSD document.',
                        nargs='?', type=argparse.FileType('wb'), default=stdout)
    opt = parser.parse_args(sys.argv[1:] if argv is None else argv)

    logger.info('Generating XSD for Python module: %s' % opt.module)
    module = imp.load_source('module.name', opt.module)
    tree = generate_xsd(getattr(module, 'Schema'))

    opt.output.write(etree.tostring(tree, pretty_print=True))

    return 0


if __name__ == '__main__':

    sys.exit(main())
