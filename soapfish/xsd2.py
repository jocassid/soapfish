from __future__ import absolute_import

from lxml import etree


XSD_NAMESPACE = 'http://www.w3.org/2001/XMLSchema'

class ElementFormDefault(object):
    QUALIFIED = 'qualified'
    UNQUALIFIED = 'unqualified'

class Schema2:
    def __init__(
            self,
            targetNamespace,
            elementFormDefault=ElementFormDefault.UNQUALIFIED,
            simpleTypes=[],
            attributeGroups=[],
            groups=[],
            complexTypes=[],
            elements={},
            imports=(),
            includes=(),
            location=None,
            targetNamespacePrefix='sns'):
        """Init arguments copied from prior version of schema for backwards compatibility"""
        self.root = etree.Element(
            '{%s}schema' % XSD_NAMESPACE,
            nsmap={
                targetNamespacePrefix: targetNamespace,
                'xsd': XSD_NAMESPACE,
            })
        self.elements = []

def main():
    target_namespace = 'http://python.org'
    schema = Schema2(target_namespace, targetNamespacePrefix='test')
    print(etree.tostring(schema.root))

if __name__ == '__main__':
    main()