@description('Name prefix for all resources')
param namePrefix string = 'taxai'
param location string = resourceGroup().location
param environment string = 'dev'

output deploymentNotes string = 'Tax Mapping service infrastructure placeholder. Add real resources here.'
