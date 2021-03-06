GLClient.
controller("ModalCtrl", ["$scope", "$uibModalInstance", function($scope, $uibModalInstance) {
  $scope.close = function() {
    $uibModalInstance.close(false);
  };

  $scope.ok = function() {
    $uibModalInstance.close(true);
  };
}]).
controller("ConfirmableDialogCtrl", ["$scope", "$uibModalInstance", "arg", function($scope, $uibModalInstance, arg) {
  $scope.arg = arg;

  $scope.ok = function (result) {
    $uibModalInstance.close(result);
  };

  $scope.cancel = function () {
    $uibModalInstance.dismiss("cancel");
  };
}]);

GLClient.controller("DisclaimerModalCtrl", ["$scope", "$rootScope", "$uibModalInstance",
                    function($scope, $rootScope, $uibModalInstance) {
  $scope.ok = function () {
    $uibModalInstance.close();
    $rootScope.setPage("submissionpage");
  };
}]);
