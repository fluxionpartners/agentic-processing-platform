@description('Name prefix for all resources')
param namePrefix string = 'taxai'
param location string = resourceGroup().location
param environment string = 'dev'

output deploymentNotes string = 'Audit and Monitoring service infrastructure placeholder. Add real resources here.'
