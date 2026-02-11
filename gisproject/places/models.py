from django.contrib.gis.db import models

class Place(models.Model):

    DATA_TYPES = (
        ('physical', 'Physical Survey'),
        ('ofc', 'OFC Record'),
    )
    name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    source_filename = models.CharField(max_length=255, blank=True, null=True)
    data_type = models.CharField(max_length=20, choices=DATA_TYPES, default='physical')
    geom = models.GeometryField(srid=4326,dim=3)
    state = models.CharField(max_length=100, db_index=True) #def
    district = models.CharField(max_length=100, db_index=True)
    block = models.CharField(max_length=100, db_index=True)

    def __str__(self):
        return f"{self.state} | {self.district} | {self.block} | {self.name}"