"""Bundle pinned official Lucide SVG assets under the platform's semantic keys."""
import io
import tarfile
from pathlib import Path
from urllib.request import urlopen
import xml.etree.ElementTree as ET

VERSION = '1.53.0'
PACKAGE = f'https://registry.npmjs.org/lucide-static/-/lucide-static-{VERSION}.tgz'
ALIASES = {
    'gauge':'gauge', 'sliders-horizontal':'sliders-horizontal', 'pulse':'activity',
    'clock-counter-clockwise':'history', 'chart-line-up':'chart-line', 'arrow-square-out':'square-arrow-out-up-right',
    'arrow-clockwise':'rotate-cw', 'caret-down':'chevron-down', 'caret-right':'chevron-right',
    'play':'play', 'stop':'square', 'shield-check':'shield-check', 'check':'check', 'file-text':'file-text',
    'download-simple':'download', 'terminal-window':'square-terminal', 'plus':'plus',
    'magnifying-glass':'search', 'x':'x', 'copy':'copy', 'arrows-out':'maximize',
    'database':'database', 'queue':'list-ordered', 'tree-structure':'workflow', 'hourglass':'hourglass',
    'calendar':'calendar-days', 'arrow-right':'arrow-right', 'sidebar-simple':'panel-left',
    'bookmark-simple':'bookmark', 'columns':'columns-3', 'minus':'minus', 'timer':'timer',
    'hash':'hash', 'brackets-curly':'braces', 'arrow-up':'arrow-up', 'arrow-down':'arrow-down',
    'arrow-left':'arrow-left', 'arrow-elbow-down-left':'corner-down-left', 'warning-circle':'circle-alert',
    'floppy-disk':'save', 'arrows-out-line-vertical':'chevrons-up-down',
    'arrows-in-line-vertical':'chevrons-down-up', 'funnel':'funnel', 'chart-bar-horizontal':'chart-bar',
    'arrow-counter-clockwise':'rotate-ccw',
}


def main():
    with urlopen(PACKAGE, timeout=30) as response:
        package = response.read()
    with tarfile.open(fileobj=io.BytesIO(package)) as archive:
        assets = {name: ET.fromstring(archive.extractfile(f'package/icons/{name}.svg').read())
                  for name in sorted(set(ALIASES.values()))}
        license = archive.extractfile('package/LICENSE').read().decode()
    sprite=ET.Element('svg',{'xmlns':'http://www.w3.org/2000/svg','data-icon-library':'lucide','data-icon-version':VERSION})
    for alias,name in ALIASES.items():
        source=assets[name]
        attributes = {key:value for key,value in source.attrib.items() if key not in ('width','height','class')}
        symbol=ET.SubElement(sprite,'symbol',{'id':alias,'data-lucide':name,**attributes})
        for child in source:
            clone=ET.fromstring(ET.tostring(child))
            for element in clone.iter():element.tag=element.tag.split('}')[-1]
            symbol.append(clone)
    root=Path(__file__).resolve().parents[2]
    output=ET.tostring(sprite,encoding='unicode')+'\n'
    (root/'performance/web/icons.svg').write_text(output,encoding='utf-8')
    (root/'frontend/public/icons.svg').write_text(output,encoding='utf-8')
    (root/'performance/web/LUCIDE-LICENSE').write_text(license,encoding='utf-8')
    print(f'Bundled {len(ALIASES)} semantic keys from official Lucide {VERSION}')


if __name__=='__main__':main()
