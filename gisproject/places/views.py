import zipfile, os, tempfile
from django.shortcuts import render, redirect
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry
from .forms import KMZUploadForm
from .models import Place
from django.core.serializers import serialize
from django.http import HttpResponse
from django.db.models import Sum
import xml.etree.ElementTree as ET
from geopy.distance import geodesic
from django.contrib.gis.db.models.functions import Length, Union as GISUnion
from django.contrib.gis.db.models.aggregates import Collect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect




from django.db.models import Count, Sum
from django.contrib.gis.db.models.functions import Length

def homepage(request):
    # Total Number of unique files uploaded
    total_files = Place.objects.values('source_filename').distinct().count()

    # Total Physical Length (Across all states/blocks)
    phys_agg = Place.objects.filter(data_type='physical').aggregate(
        total=Sum(Length('geom', geography=True))
    )
    # Total OFC Length (Across all states/blocks)
    ofc_agg = Place.objects.filter(data_type='ofc').aggregate(
        total=Sum(Length('geom', geography=True))
    )

    phys_km = phys_agg['total'].km if phys_agg['total'] else 0.0
    ofc_km = ofc_agg['total'].km if ofc_agg['total'] else 0.0
    deviation = abs(phys_km - ofc_km)

    context = {
        'total_files': total_files,
        'phys_km': round(phys_km, 2),
        'ofc_km': round(ofc_km, 2),
        'deviation': round(deviation, 2),
    }
    return render(request, 'places/homepage.html', context)





# Helper function to check if user is an Admin
def is_admin(user):
    return user.is_authenticated and user.is_staff

"""
@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def upload_kmz(request):
    if request.method == 'POST':
        form = KMZUploadForm(request.POST, request.FILES)
        if form.is_valid():
            kmz_file = request.FILES['kmz_file']
            dtype = form.cleaned_data['data_type']
            
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(kmz_file, 'r') as z:
                    kml_name = next((f for f in z.namelist() if f.endswith('.kml')), None)
                    if kml_name:
                        z.extract(kml_name, tmpdir)
                        ds = DataSource(os.path.join(tmpdir, kml_name))
                        for layer in ds:
                            for feature in layer:
                                geom = GEOSGeometry(feature.geom.wkt, srid=4326)
                                # Flatten 3D to 2D if necessary
                                if geom.hasz: 
                                    geom = GEOSGeometry(geom.wkb, srid=4326)
                                description_data = feature.get('Description') or feature.get('description') or ""
                                
                                Place.objects.create(
                                    name=feature.get('Name') or "Unnamed",
                                    data_type=dtype,
                                    source_filename=kmz_file.name,
                                    geom=geom,
                                    description=description_data
                                )
            return redirect('comparison_map')
    else:
        form = KMZUploadForm()
    return render(request, 'places/upload.html', {'form': form})"""
 
import re

def get_kml_data(kml_content):
    styles = {}
    style_maps = {}
    id_to_style = {}
    name_to_style = {}

    try:
        kml_str = kml_content.decode('utf-8', errors='ignore')

        # 1. Extract LineStyle colors from global Styles
        style_ids = re.findall(r'<Style\s+id="([^"]+)">.*?</Style>', kml_str, re.DOTALL)

        for s_id in style_ids:
            block_match = re.search(
                rf'<Style\s+id="{re.escape(s_id)}">.*?</Style>',
                kml_str,
                re.DOTALL
            )

            if block_match:
                block = block_match.group(0)

                # Only grab LineStyle color (NOT icon or label)
                color_match = re.search(
                    r'<LineStyle>.*?<color>\s*([a-fA-F0-9]{8})\s*</color>',
                    block,
                    re.DOTALL
                )

                if color_match:
                    c = color_match.group(1)
                    r = c[6:8]
                    g = c[4:6]
                    b = c[2:4]
                    styles[s_id] = f"#{r}{g}{b}".lower()

        # 2. Extract StyleMaps → map to actual style IDs
        sm_blocks = re.findall(r'<StyleMap\s+id="([^"]+)">.*?</StyleMap>', kml_str, re.DOTALL)

        for sm_id in sm_blocks:
            sm_match = re.search(
                rf'<StyleMap\s+id="{re.escape(sm_id)}">.*?</StyleMap>',
                kml_str,
                re.DOTALL
            )

            if sm_match:
                url_match = re.search(
                    r'<styleUrl>#?(.*?)</styleUrl>',
                    sm_match.group(0)
                )

                if url_match:
                    style_maps[sm_id] = url_match.group(1).strip()

        # 3. Map placemarks → styles
        placemark_blocks = re.findall(
            r'<Placemark[^>]*>.*?</Placemark>',
            kml_str,
            re.DOTALL
        )

        for block in placemark_blocks:
            p_id_match = re.search(r'id="([^"]+)"', block)
            p_name_match = re.search(r'<name>(.*?)</name>', block)
            p_style_match = re.search(r'<styleUrl>#?(.*?)</styleUrl>', block)

            if p_style_match:
                raw_id = p_style_match.group(1).strip()
                final_style_id = style_maps.get(raw_id, raw_id)

                if p_id_match:
                    id_to_style[p_id_match.group(1)] = final_style_id

                if p_name_match:
                    clean_name = re.sub(
                        r'<!\[CDATA\[(.*?)\]\]>',
                        r'\1',
                        p_name_match.group(1)
                    ).strip()

                    name_to_style[clean_name] = final_style_id

    except Exception as e:
        print(f"--- KML Logic Error: {e} ---")

    return styles, id_to_style, name_to_style

@login_required
def upload_kmz(request):
    if request.method == 'POST':
        form = KMZUploadForm(request.POST, request.FILES)

        if form.is_valid():
            kmz_file = request.FILES['kmz_file']
            dtype = request.POST.get('data_type')
            state = request.POST.get('state')
            district = request.POST.get('district')
            block = request.POST.get('block')

            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(kmz_file, 'r') as z:
                    kml_name = next((f for f in z.namelist() if f.endswith('.kml')), None)

                    if kml_name:
                        kml_content = z.read(kml_name)

                        styles_map, id_map, name_map = get_kml_data(kml_content)

                        print(f"--- DEBUG: Styles Extracted ---")
                        print(styles_map)

                        kml_str = kml_content.decode('utf-8', errors='ignore')

                        z.extract(kml_name, tmpdir)
                        ds = DataSource(os.path.join(tmpdir, kml_name))

                        placemark_blocks = re.findall(
                            r'<Placemark[^>]*>.*?</Placemark>',
                            kml_str,
                            re.DOTALL
                        )

                        for layer in ds:
                            for idx, feature in enumerate(layer):

                                geom = GEOSGeometry(feature.geom.wkt, srid=4326)
                                if geom.hasz:
                                    geom = GEOSGeometry(geom.wkb, srid=4326)

                                f_name = feature.get('Name')
                                f_id = feature.get('id') or str(feature.fid)

                                # Match XML placemark block
                                block_xml = placemark_blocks[idx] if idx < len(placemark_blocks) else ""

                                # Inline style color check
                                inline_color = re.search(
                                    r'<LineStyle>.*?<color>\s*([a-fA-F0-9]{8})\s*</color>',
                                    block_xml,
                                    re.DOTALL
                                )

                                if inline_color:
                                    c = inline_color.group(1)
                                    hex_color = f"#{c[6:8]}{c[4:6]}{c[2:4]}".lower()
                                else:
                                    s_id = name_map.get(f_name) or id_map.get(f_id)
                                    if not s_id:
                                        s_id = id_map.get(f"ID_{str(f_id).zfill(5)}")

                                    hex_color = styles_map.get(s_id, "")

                                print("PLACEMARK:", f_name, "COLOR:", hex_color)

                                Place.objects.create(
                                    name=f_name or "Unnamed",
                                    data_type=dtype,
                                    state=state,
                                    district=district,
                                    block=block,
                                    description=feature.get('Description') or "",
                                    source_filename=kmz_file.name,
                                    line_color=hex_color,
                                    geom=geom
                                )

            return redirect('comparison_map')

    else:
        form = KMZUploadForm()

    return render(request, 'places/upload.html', {'form': form})


def calculate_python_length(queryset):
     
    total_km = 0.0
    for place in queryset:
        if place.geom and place.geom.geom_type in ['LineString', 'MultiLineString']:
            
            lines = place.geom if place.geom.geom_type == 'MultiLineString' else [place.geom]
            
            for line in lines:
                coords = line.coords  
                for i in range(len(coords) - 1):
                    
                    point_a = (coords[i][1], coords[i][0])
                    point_b = (coords[i+1][1], coords[i+1][0])
                    total_km += geodesic(point_a, point_b).km
    return total_km

@login_required
def comparison_map(request):
    all_states = Place.objects.values_list('state', flat=True).distinct().order_by('state')
    all_districts = Place.objects.values_list('district', flat=True).distinct().order_by('district')
    all_blocks = Place.objects.values_list('block', flat=True).distinct().order_by('block')

    state_filter = request.GET.get('state')
    dist_filter = request.GET.get('district')
    block_filter = request.GET.get('block')

    
    physical_data = Place.objects.none()
    ofc_data = Place.objects.none()

    
    if state_filter or dist_filter or block_filter:
        physical_data = Place.objects.filter(data_type='physical')
        ofc_data = Place.objects.filter(data_type='ofc')

        if state_filter:
            physical_data = physical_data.filter(state__iexact=state_filter)
            ofc_data = ofc_data.filter(state__iexact=state_filter)
        if dist_filter:
            physical_data = physical_data.filter(district__iexact=dist_filter)
            ofc_data = ofc_data.filter(district__iexact=dist_filter)
        if block_filter:
            physical_data = physical_data.filter(block__iexact=block_filter)
            ofc_data = ofc_data.filter(block__iexact=block_filter)

    # 1. Calculate Lengths (Will naturally result in 0 if no data)
    phys_agg = physical_data.aggregate(total=Sum(Length('geom', geography=True)))
    ofc_agg = ofc_data.aggregate(total=Sum(Length('geom', geography=True)))
    
    phys_km_val = phys_agg['total'].km if phys_agg['total'] else 0.0
    ofc_km_val = ofc_agg['total'].km if ofc_agg['total'] else 0.0

    # 2. Spatial Analysis for Orange Deviations
    phys_coll = physical_data.aggregate(combined=Collect('geom'))['combined']
    ofc_coll = ofc_data.aggregate(combined=Collect('geom'))['combined']


    py_phys_km = calculate_python_length(physical_data) if physical_data.exists() else 0.0
    py_ofc_km = calculate_python_length(ofc_data) if ofc_data.exists() else 0.0

    deviation_json = None
    if phys_coll and ofc_coll:
        phys_union = phys_coll.unary_union
        ofc_union = ofc_coll.unary_union
        phys_buffer = phys_union.transform(3857, clone=True).buffer(2).transform(4326, clone=True)
        deviation_geom = ofc_union.difference(phys_buffer)
        
        if deviation_geom and not deviation_geom.empty:
            deviation_json = deviation_geom.json
    
    # PRINT TO DJANGO SERVER CONSOLE
    print("\n" + "="*50)
    print(f" AUDIT REPORT for BLOCK: {block_filter or 'All'}")
    print("="*50)
    print(f"{'DATA TYPE':<15} | {'POSTGIS (DB)':<15} | {'GEOPY (PY)':<15}")
    print("-" * 50)
    print(f"{'PHYSICAL':<15} | {phys_km_val:>12.4f} km | {py_phys_km:>10.4f} km")
    print(f"{'OFC':<15} | {ofc_km_val:>12.4f} km | {py_ofc_km:>10.4f} km")
    
    # Calculate Variance
    phys_diff = abs(phys_km_val - py_phys_km)
    ofc_diff = abs(ofc_km_val   - py_ofc_km)
    
    print("-" * 50)
    print(f"PHYS Variance: {phys_diff:.6f} km")
    print(f"OFC  Variance: {ofc_diff:.6f} km")
    print("="*50 + "\n")

    context = {
        'physical_places': physical_data,
        'ofc_places': ofc_data,
        'deviation_json': deviation_json,
        'phys_km': round(phys_km_val, 2),
        'ofc_km': round(ofc_km_val, 2),
        'diff_km': round(abs(phys_km_val - ofc_km_val), 2),
        'states': all_states,
        'districts': all_districts,
        'blocks': all_blocks,
        'audit': {
            'phys_db': round(phys_km_val, 4),
            'phys_py': round(py_phys_km, 4),
            'ofc_db': round(ofc_km_val, 4),
            'ofc_py': round(py_ofc_km, 4),
        },
    }
    return render(request, 'places/comparison.html', context)

def map_view(request):
    places = Place.objects.all()
    return render(request, 'places/map.html', {'places': places})

def export_geojson(request):
    data = Place.objects.all()
    geojson_data = serialize('geojson', data, geometry_field='geom', fields=('name', 'description', 'source_filename'))
    response = HttpResponse(geojson_data, content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename="exported_data.geojson"'
    return response