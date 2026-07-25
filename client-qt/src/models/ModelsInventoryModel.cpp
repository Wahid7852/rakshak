#include "rakshak/models/ModelsInventoryModel.h"
#include <QtGui/QStandardItemModel>

ModelsInventoryModel::ModelsInventoryModel(QObject* parent) : QStandardItemModel(parent) {
    setHorizontalHeaderLabels({"Name","Version","Size (MB)","Checksum","Date"});
}