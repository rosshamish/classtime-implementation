// Classes Controller
//

coreModule.controller('fastCourseListCtrl', ['$scope', '$window', 'fastCourseFactory', '$timeout', function($scope, $window, fastCourseFactory, $timeout) {

	// New, organized course object
	$scope.subjectBin = {};
	var subjectBin = {};

	// temp used in transfer to new course object
	var pageListing;

    // Counters
    var page  = 1;
    var total_pages;

    // Purpose of first call to getCoursesPage is to get total_pages
    fastCourseFactory.getCoursesPage(1).
    success(function (data, status, headers, config) {
            // De-serialize JSON data
            pageListing = angular.fromJson(data);
            total_pages = pageListing.total_pages;

            // In these calls, actually get and arrange the data
            while (page < (total_pages + 1)) {
                fastCourseFactory.getCoursesPage(page).
                    success(function (data, status, headers, config) {
                        // De-serialize JSON data
                        pageListing = angular.fromJson(data);

                        // For each course on page of results...
                        pageListing.objects.forEach(function (course) {
                            if (subjectBin.hasOwnProperty(course.faculty)) {
                                // We are within an existing faculty property
                                if (subjectBin[course.faculty].hasOwnProperty(course.subject)) {
                                    subjectBin[course.faculty][course.subject].push(course.asString);
                                }
                                else {
                                    subjectBin[course.faculty][course.subject] = [course.asString];
                                }
                            }
                            else {
                                subjectBin[course.faculty] = {};
                                subjectBin[course.faculty][course.subject] = [course.asString];

                            }
                        });
                    }).
                    error(function () {
                        $window.alert("Sorry, something went wrong.");
                    });

                page = page + 1;
            }
    }).
    error(function () {
            $window.alert("Sorry, something went wrong.");
    });


	// Gather new object received from the above
	$scope.subjectBin = subjectBin;


    // Filter watcher
    //
    // This watches the ng-model called "searchBox" and changes the $scope filter, filterText, every 0.5 second
    // It is affecting the regular $digest cycle, which is normally on every state change of the input (new text)
    $scope.filterText = '';
	var tempFilterText = '';
	var filterTextTimeout;
	$scope.$watch('searchBox', function(val) {
		if (filterTextTimeout) {
			$timeout.cancel(filterTextTimeout);
		}
		tempFilterText = val;
		filterTextTimeout = $timeout(function() {
			$scope.filterText = tempFilterText;
		}, 500);
	});

}]);



