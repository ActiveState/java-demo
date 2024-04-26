import os

from io import BytesIO
from lxml import etree
from pathlib import Path
from sys import argv
from typing import Any


def add_text_elem(parent, tag, text):
    node = etree.SubElement(parent, tag)
    node.text = text

def add_dependency(group, artifact, version) -> etree.Element:
    dep = etree.Element('dependency')

    add_text_elem(dep, 'groupId', group)
    add_text_elem(dep, 'artifactId', artifact)
    add_text_elem(dep, 'version', version)

    return dep

def get_xml_root(file: str) -> Any:
    # Following is a gross hack to work around XML files containing HTML
    # entities - well, really just one entity right now. I don't know how to
    # properly solve this - maybe some sort of DTD shenanigans defining HTML
    # entities?
    with open(file) as fp:
        contents = fp.read()
        contents = contents.replace("&oslash;", "ø")

    parser = etree.XMLParser()
    pom = etree.parse(BytesIO(bytes(contents, "utf-8")), parser)
    root = pom.getroot()

    return root

def main(project_name: str, m2_root: Path) -> None:
    full_pom_paths = m2_root.glob("**/*.pom")

    # create top-level element
    project = etree.Element('project')
    project_attrs = project.attrib

    project_attrs["xmlns"] = "http://maven.apache.org/POM/4.0.0"
    project_attrs["{http://maven.apache.org/POM/4.0.0}xsi"] = "http://www.w3.org/2001/XMLSchema-instance"
    project_attrs["{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"] = "http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd"

    # add basic dependency elements
    add_text_elem(project, 'modelVersion', '4.0.0')
    add_text_elem(project, 'groupId', 'com.activestate.platform.project')
    add_text_elem(project, 'artifactId', project_name)
    add_text_elem(project, 'version', '1.0.0')
    add_text_elem(project, 'packaging', 'pom')
    add_text_elem(project, 'name', project_name)
    add_text_elem(project, 'description', 'platform project bom')

    dep_management = etree.SubElement(project, 'dependencyManagement')
    deps = etree.SubElement(dep_management, 'dependencies')

    dependencies = {}
    for full_pom_path in sorted(full_pom_paths):
        # Example pom path: io/vavr/vavr-match/0.9.3/vavr-match-0.9.3.pom
        pom_path = full_pom_path.relative_to(m2_root)

        parts = pom_path.parts
        group_id = ".".join(parts[:-3])
        artifact_id = parts[-3]
        version = parts[-2]

        root = get_xml_root(str(full_pom_path))

        packaging_node = root.find("packaging", root.nsmap)
        if packaging_node is None:
            packaging = "jar"
        else:
            packaging = packaging_node.text

        if packaging == "pom" or packaging == "plugin":
            continue

        ga = ":".join([group_id, artifact_id])
        if ga in dependencies:
            old_version = dependencies[ga].split(".")
            new_version = version.split(".")
            if new_version > old_version:
                dependencies[ga] = version
        else:
            dependencies[ga] = version

    for dep, version in dependencies.items():
        dep_elem = etree.SubElement(deps, 'dependency')
        (groupId, artifactId) = dep.split(":", 2)
        add_text_elem(dep_elem, 'groupId', groupId)
        add_text_elem(dep_elem, 'artifactId', artifactId)
        add_text_elem(dep_elem, 'version', version)

    # write the file
    et = etree.ElementTree(project)
    bom_filename = project_name + "-bom"
    bom_root = m2_root / "com" / "activestate" / "platform" / "project" / bom_filename / "1.0.0"
    bom_root.mkdir(parents=True, exist_ok=True)

    bom_path = bom_root / (bom_filename + "-1.0.0.pom")
    print(bom_path)
    et.write(str(bom_path), pretty_print=True)

if __name__ == "__main__":
    if len(argv) < 2:
        raise RuntimeError("project_name is required.")

    project_name = argv[1]

    if len(argv) < 3:
        java_home = os.environ.get("JAVA_HOME")
        if not java_home:
            raise RuntimeError("JAVA_HOME is unset - BOM generation requires an active project with a JDK present or the path to the M2 directory.")
        m2_root = Path(java_home).parent / "m2"
    else:
        m2_root = Path(argv[2])


    main(project_name=project_name, m2_root=m2_root)
