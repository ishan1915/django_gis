import zipfile, os, tempfile
from django.shortcuts import render, redirect
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry
from .forms import KMZUploadForm
from .models import Place
from django.core.serializers import serialize
from django.http import HttpResponse
from django.db.models import Sum

# Use specific aliases to avoid naming collisions with standard Django models
from django.contrib.gis.db.models.functions import Length, Union as GISUnion
from django.contrib.gis.db.models.aggregates import Collect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect

# Helper function to check if user is an Admin
def is_admin(user):
    return user.is_authenticated and user.is_staff

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
    return render(request, 'places/upload.html', {'form': form})

@login_required
def comparison_map(request):
    # Always fetch these so the dropdowns are populated on page load
    all_states = Place.objects.values_list('state', flat=True).distinct().order_by('state')
    all_districts = Place.objects.values_list('district', flat=True).distinct().order_by('district')
    all_blocks = Place.objects.values_list('block', flat=True).distinct().order_by('block')

    state_filter = request.GET.get('state')
    dist_filter = request.GET.get('district')
    block_filter = request.GET.get('block')

    # FIX: Initialize with an empty QuerySet
    physical_data = Place.objects.none()
    ofc_data = Place.objects.none()

    # Only perform database queries if a filter is applied
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

    deviation_json = None
    if phys_coll and ofc_coll:
        phys_union = phys_coll.unary_union
        ofc_union = ofc_coll.unary_union
        phys_buffer = phys_union.transform(3857, clone=True).buffer(2).transform(4326, clone=True)
        deviation_geom = ofc_union.difference(phys_buffer)
        
        if deviation_geom and not deviation_geom.empty:
            deviation_json = deviation_geom.json

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