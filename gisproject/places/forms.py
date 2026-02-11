from django import forms

class KMZUploadForm(forms.Form):
    kmz_file = forms.FileField(label="Select a KMZ file")
    data_type = forms.ChoiceField(choices=(('physical', 'Physical Survey'), ('ofc', 'OFC Record')))
    state = forms.CharField(max_length=100, initial="Punjab")
    district = forms.CharField(max_length=100, initial="Moga")
    block = forms.CharField(max_length=100, initial="Nihal Singh Wala")